from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field

from job_finder.config import AppConfig
from job_finder.models import Job, Recommendation
from job_finder.utils import normalize_whitespace

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "we",
    "will",
    "with",
    "you",
    "your",
}
TOKEN_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-/]{1,30}")
YEARS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)", re.IGNORECASE)
JSON_BLOCK_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)


def tokenize(text: str) -> list[str]:
    tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text or "")]
    return [token for token in tokens if token not in STOPWORDS]


def extract_keywords(text: str, limit: int = 20) -> list[str]:
    counts = Counter(tokenize(text))
    return [token for token, _ in counts.most_common(limit)]


def lexical_similarity(left: str, right: str) -> float:
    left_counts = Counter(tokenize(left))
    right_counts = Counter(tokenize(right))
    if not left_counts or not right_counts:
        return 0.0
    shared = sum(left_counts[token] * right_counts[token] for token in left_counts.keys() & right_counts.keys())
    left_norm = math.sqrt(sum(value * value for value in left_counts.values()))
    right_norm = math.sqrt(sum(value * value for value in right_counts.values()))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, shared / (left_norm * right_norm)))


def estimate_years_required(text: str) -> float | None:
    matches = [float(match.group(1)) for match in YEARS_PATTERN.finditer(text or "")]
    return max(matches) if matches else None


def normalize_company_name(value: str) -> str:
    return normalize_whitespace(value).lower()


def _extract_json_score(text: str) -> float | None:
    if not text:
        return None
    match = JSON_BLOCK_PATTERN.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    score = payload.get("score")
    if isinstance(score, (int, float)):
        return max(0.0, min(1.0, float(score)))
    return None


class OptionalGroqScorer:
    def __init__(self, config: AppConfig, resume_text: str) -> None:
        self.enabled = False
        self._client = None
        self._model = config.groq.model.strip()
        self._resume_text = resume_text[:6000]

        api_key = os.getenv(config.groq.api_key_env, "")
        if not config.groq.enabled or not api_key or not self._model:
            return

        try:
            from groq import Groq
        except ImportError:
            return

        self._client = Groq(api_key=api_key)
        self.enabled = True

    def score(self, job_text: str) -> float | None:
        if not self.enabled or not self._client:
            return None

        prompt = (
            "Evaluate how well this resume matches this job. "
            "Return only compact JSON like {\"score\": 0.82}. "
            "Use a score between 0 and 1 where 1 is an excellent fit."
            f"\n\nResume:\n{self._resume_text}"
            f"\n\nJob:\n{job_text[:6000]}"
        )
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                max_tokens=40,
                messages=[
                    {
                        "role": "system",
                        "content": "You score resume-to-job fit. Respond with JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception:
            return None

        if not response.choices:
            return None
        content = response.choices[0].message.content or ""
        return _extract_json_score(content)


@dataclass(slots=True)
class JobMatcher:
    config: AppConfig
    resume_text: str
    weights: dict[str, float] = field(init=False)
    resume_keywords: set[str] = field(init=False)
    target_titles: list[str] = field(init=False)
    target_skills: set[str] = field(init=False)
    preferred_companies: set[str] = field(init=False)
    groq_scorer: OptionalGroqScorer = field(init=False)

    def __post_init__(self) -> None:
        self.weights = self.config.scoring_weights.normalized()
        self.resume_keywords = set(extract_keywords(self.resume_text, limit=60))
        self.target_titles = [value.lower() for value in self.config.profile.target_titles]
        self.target_skills = {
            value.lower()
            for value in (self.config.profile.must_have_skills + self.config.profile.nice_to_have_skills)
        }
        self.preferred_companies = {
            normalize_company_name(company) for company in self.config.profile.preferred_companies
        }
        self.groq_scorer = OptionalGroqScorer(self.config, self.resume_text)

    def evaluate(self, job: Job) -> Recommendation:
        job_text = normalize_whitespace(" ".join([job.title, job.company, job.location, job.description]))

        semantic_score = self.groq_scorer.score(job_text)
        if semantic_score is None:
            semantic_score = lexical_similarity(self.resume_text, job_text)

        matched_skills = sorted(skill for skill in self.target_skills if skill in job_text.lower())
        must_have_hits = [skill for skill in self.config.profile.must_have_skills if skill in job_text.lower()]
        nice_to_have_hits = [skill for skill in self.config.profile.nice_to_have_skills if skill in job_text.lower()]
        required_skills_total = (len(self.config.profile.must_have_skills) * 1.5) + len(self.config.profile.nice_to_have_skills) or 1.0
        skill_score = ((len(must_have_hits) * 1.5) + len(nice_to_have_hits)) / required_skills_total
        skill_score = max(0.0, min(1.0, skill_score))

        years_required = estimate_years_required(job.description)
        if years_required is None:
            experience_score = 0.6
        elif self.config.profile.years_experience >= years_required:
            experience_score = 1.0
        else:
            gap = years_required - self.config.profile.years_experience
            experience_score = max(0.0, 1.0 - (gap / max(years_required, 1.0)))

        company_score = float(job.metadata.get("source_quality", 0.6))
        if normalize_company_name(job.company) in self.preferred_companies:
            company_score = 1.0

        remote_pref = self.config.profile.remote_preference
        location_text = f"{job.location} {job.description}".lower()
        if remote_pref == "remote_only":
            remote_score = 1.0 if job.remote else 0.0
        elif remote_pref == "remote_or_hybrid":
            remote_score = 1.0 if job.remote else 0.6
        else:
            remote_score = 0.8
            if self.config.profile.locations:
                remote_score = 1.0 if any(location.lower() in location_text for location in self.config.profile.locations) else 0.4

        salary_floor = self.config.profile.min_salary
        if salary_floor is None:
            salary_score = 0.6
        elif job.salary_max is None and job.salary_min is None:
            salary_score = 0.35
        else:
            offered = job.salary_max or job.salary_min or 0
            if offered >= salary_floor:
                salary_score = 1.0
            else:
                salary_score = max(0.0, offered / salary_floor)

        title_boost = 0.15 if any(title in job.title.lower() for title in self.target_titles) else 0.0
        semantic_score = min(1.0, semantic_score + title_boost)

        breakdown = {
            "semantic": round(semantic_score, 4),
            "skills": round(skill_score, 4),
            "experience": round(experience_score, 4),
            "company": round(company_score, 4),
            "remote": round(remote_score, 4),
            "salary": round(salary_score, 4),
        }
        total_score = sum(breakdown[key] * self.weights[key] for key in breakdown)

        missing_skills = [
            keyword
            for keyword in extract_keywords(job.description, limit=30)
            if keyword not in self.resume_keywords and keyword not in STOPWORDS and len(keyword) > 2
        ][:8]
        accepted = total_score >= self.config.min_score and (
            not self.config.profile.must_have_skills
            or len(must_have_hits) >= max(1, len(self.config.profile.must_have_skills) // 2)
        )
        summary_bits = [
            f"score {total_score:.2f}",
            f"{len(matched_skills)} profile skills matched",
        ]
        if years_required is not None:
            summary_bits.append(f"requires ~{years_required:g} years")
        if job.remote:
            summary_bits.append("remote-friendly")
        if job.salary_min or job.salary_max:
            summary_bits.append("salary listed")
        summary = ", ".join(summary_bits)

        return Recommendation(
            job=job,
            total_score=round(total_score, 4),
            accepted=accepted,
            breakdown=breakdown,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            summary=summary,
        )
