from __future__ import annotations

from job_finder.models import Job
from job_finder.sources.base import JobSource
from job_finder.utils import fetch_json, html_to_text, parse_datetime


class GreenhouseSource(JobSource):
    def fetch_jobs(self) -> list[Job]:
        board_token = str(self.config.settings["board_token"])
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        payload = fetch_json(url)
        results: list[Job] = []

        for entry in payload.get("jobs", [])[: self.max_jobs]:
            location = (entry.get("location") or {}).get("name", "")
            description = html_to_text(entry.get("content", "") or "")
            lower_text = f"{location} {description}".lower()
            results.append(
                Job(
                    source=self.config.name,
                    external_id=str(entry.get("id")),
                    title=entry.get("title", "").strip(),
                    company=board_token.replace("-", " ").title(),
                    url=entry.get("absolute_url", ""),
                    location=location,
                    description=description,
                    remote="remote" in lower_text or "work from home" in lower_text,
                    posted_at=parse_datetime(entry.get("updated_at")),
                    metadata={
                        "department": ", ".join(dept.get("name", "") for dept in entry.get("departments", []) if dept.get("name")),
                        "source_quality": float(self.config.settings.get("quality", 0.85)),
                    },
                )
            )
        return results
