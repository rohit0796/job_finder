from __future__ import annotations

from job_finder.models import Job
from job_finder.sources.base import JobSource
from job_finder.utils import fetch_json, html_to_text, parse_datetime


class LeverSource(JobSource):
    def fetch_jobs(self) -> list[Job]:
        company = str(self.config.settings["company"])
        url = f"https://api.lever.co/v0/postings/{company}?mode=json"
        payload = fetch_json(url)
        results: list[Job] = []

        for entry in payload[: self.max_jobs]:
            categories = entry.get("categories") or {}
            location = categories.get("location") or categories.get("allLocations") or ""
            description = html_to_text(entry.get("descriptionPlain") or entry.get("description") or "")
            workplace_type = str(entry.get("workplaceType", ""))
            lower_text = f"{location} {description} {workplace_type}".lower()
            results.append(
                Job(
                    source=self.config.name,
                    external_id=str(entry.get("id")),
                    title=entry.get("text", "").strip(),
                    company=company.replace("-", " ").title(),
                    url=entry.get("hostedUrl", ""),
                    location=location,
                    description=description,
                    remote="remote" in lower_text,
                    posted_at=parse_datetime(entry.get("createdAt")),
                    metadata={
                        "team": categories.get("team", ""),
                        "commitment": categories.get("commitment", ""),
                        "source_quality": float(self.config.settings.get("quality", 0.85)),
                    },
                )
            )
        return results
