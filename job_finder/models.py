from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from job_finder.utils import utc_now


@dataclass(slots=True)
class Job:
    source: str
    external_id: str
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    remote: bool = False
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    fetched_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fingerprint(self) -> str:
        raw = "|".join(
            [
                self.source.strip().lower(),
                self.external_id.strip().lower(),
                self.title.strip().lower(),
                self.company.strip().lower(),
                self.url.strip().lower(),
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class Recommendation:
    job: Job
    total_score: float
    accepted: bool
    breakdown: dict[str, float]
    matched_skills: list[str]
    missing_skills: list[str]
    summary: str


@dataclass(slots=True)
class FetchReport:
    source_name: str
    fetched_jobs: int
    error: str | None = None


@dataclass(slots=True)
class NotificationResult:
    accepted_jobs: int
    new_jobs: int
    skipped_seen_jobs: int
    notified_jobs: int
    channels_sent: list[str]
    errors: list[str] = field(default_factory=list)
