from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("job_finder.toml")
EXAMPLE_CONFIG_PATH = Path("job_finder.example.toml")


@dataclass(slots=True)
class ProfileConfig:
    name: str = ""
    target_titles: list[str] = field(default_factory=list)
    must_have_skills: list[str] = field(default_factory=list)
    nice_to_have_skills: list[str] = field(default_factory=list)
    preferred_companies: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_preference: str = "remote_or_hybrid"
    min_salary: int | None = None
    years_experience: float = 0.0
    max_experience_gap: float = 2.0


@dataclass(slots=True)
class ScoringWeights:
    semantic: float = 0.35
    skills: float = 0.25
    experience: float = 0.15
    company: float = 0.10
    remote: float = 0.10
    salary: float = 0.05

    def normalized(self) -> dict[str, float]:
        raw = {
            "semantic": self.semantic,
            "skills": self.skills,
            "experience": self.experience,
            "company": self.company,
            "remote": self.remote,
            "salary": self.salary,
        }
        total = sum(raw.values()) or 1.0
        return {key: value / total for key, value in raw.items()}


@dataclass(slots=True)
class GroqConfig:
    enabled: bool = False
    api_key_env: str = "GROQ_API_KEY"
    model: str = ""


@dataclass(slots=True)
class TelegramConfig:
    enabled: bool = False
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id: str = ""

    @property
    def bot_token(self) -> str:
        return os.getenv(self.bot_token_env, "")


@dataclass(slots=True)
class EmailConfig:
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    username: str = ""
    password_env: str = "EMAIL_APP_PASSWORD"
    from_address: str = ""
    to_address: str = ""
    use_ssl: bool = True

    @property
    def password(self) -> str:
        return os.getenv(self.password_env, "")


@dataclass(slots=True)
class SourceConfig:
    type: str
    name: str
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AppConfig:
    config_path: Path
    seen_store: str
    seen_jobs_path: Path
    seen_jobs_blob_path: str
    resume_path: Path
    top_k: int
    min_score: float
    max_jobs_per_source: int
    profile: ProfileConfig
    scoring_weights: ScoringWeights
    groq: GroqConfig
    telegram: TelegramConfig | None
    email: EmailConfig | None
    sources: list[SourceConfig]


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (base_dir / path).resolve()


def _read_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    return value if isinstance(value, dict) else {}


def load_config(path: Path | None = None) -> AppConfig:
    config_path = (path or DEFAULT_CONFIG_PATH).resolve()
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    base_dir = config_path.parent

    app_table = _read_table(raw, "app")
    profile_table = _read_table(raw, "profile")
    scoring_table = _read_table(_read_table(raw, "scoring"), "weights")
    groq_table = _read_table(raw, "groq")
    notifications_table = _read_table(raw, "notifications")
    telegram_table = _read_table(notifications_table, "telegram")
    email_table = _read_table(notifications_table, "email")

    profile = ProfileConfig(
        name=profile_table.get("name", ""),
        target_titles=list(profile_table.get("target_titles", [])),
        must_have_skills=[value.lower()
                          for value in profile_table.get("must_have_skills", [])],
        nice_to_have_skills=[value.lower() for value in profile_table.get(
            "nice_to_have_skills", [])],
        preferred_companies=list(profile_table.get("preferred_companies", [])),
        locations=list(profile_table.get("locations", [])),
        remote_preference=profile_table.get(
            "remote_preference", "remote_or_hybrid"),
        min_salary=profile_table.get("min_salary"),
        years_experience=float(profile_table.get("years_experience", 0.0)),
    )
    scoring_weights = ScoringWeights(
        semantic=float(scoring_table.get("semantic", 0.35)),
        skills=float(scoring_table.get("skills", 0.25)),
        experience=float(scoring_table.get("experience", 0.15)),
        company=float(scoring_table.get("company", 0.10)),
        remote=float(scoring_table.get("remote", 0.10)),
        salary=float(scoring_table.get("salary", 0.05)),
    )
    groq = GroqConfig(
        enabled=bool(groq_table.get("enabled", False)),
        api_key_env=groq_table.get("api_key_env", "GROQ_API_KEY"),
        model=groq_table.get("model", ""),
    )
    telegram = TelegramConfig(
        enabled=bool(telegram_table.get("enabled", False)),
        bot_token_env=telegram_table.get(
            "bot_token_env", "TELEGRAM_BOT_TOKEN"),
        chat_id=telegram_table.get("chat_id", ""),
    )
    email = EmailConfig(
        enabled=bool(email_table.get("enabled", False)),
        smtp_host=email_table.get("smtp_host", ""),
        smtp_port=int(email_table.get("smtp_port", 465)),
        username=email_table.get("username", ""),
        password_env=email_table.get("password_env", "EMAIL_APP_PASSWORD"),
        from_address=email_table.get("from_address", ""),
        to_address=email_table.get("to_address", ""),
        use_ssl=bool(email_table.get("use_ssl", True)),
    )

    sources: list[SourceConfig] = []
    for entry in raw.get("sources", []):
        if not isinstance(entry, dict):
            continue
        payload = dict(entry)
        source_type = str(payload.pop("type"))
        name = str(payload.pop("name", source_type))
        enabled = bool(payload.pop("enabled", True))
        sources.append(SourceConfig(type=source_type, name=name,
                       enabled=enabled, settings=payload))

    return AppConfig(
        config_path=config_path,
        seen_store=str(app_table.get("seen_store", "local_json")),
        seen_jobs_path=_resolve_path(base_dir, app_table.get(
            "seen_jobs_path", ".job_finder/seen_jobs.json")),
        seen_jobs_blob_path=str(app_table.get(
            "seen_jobs_blob_path", "job-finder/seen_jobs.json")),
        resume_path=_resolve_path(
            base_dir, app_table.get("resume_path", "resume.txt")),
        top_k=int(app_table.get("top_k", 15)),
        min_score=float(app_table.get("min_score", 0.58)),
        max_jobs_per_source=int(app_table.get("max_jobs_per_source", 40)),
        profile=profile,
        scoring_weights=scoring_weights,
        groq=groq,
        telegram=telegram,
        email=email,
        sources=sources,
    )


def write_example_config(destination: Path | None = None) -> Path:
    target = (destination or DEFAULT_CONFIG_PATH).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    example_path = Path.cwd() / EXAMPLE_CONFIG_PATH
    if example_path.exists():
        shutil.copyfile(example_path, target)
        return target
    target.write_text("", encoding="utf-8")
    return target
