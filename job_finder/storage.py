from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from job_finder.config import AppConfig
from job_finder.models import Recommendation
from job_finder.utils import utc_now


class SeenJobsStore(ABC):
    @abstractmethod
    def get_seen_fingerprints(self, fingerprints: list[str]) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def mark_jobs_seen(self, recommendations: list[Recommendation], channels: list[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_seen_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def location_label(self) -> str:
        raise NotImplementedError


class LocalJSONSeenJobsStore(SeenJobsStore):
    def __init__(self, seen_jobs_path: Path) -> None:
        self.seen_jobs_path = seen_jobs_path
        self.seen_jobs_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def location_label(self) -> str:
        return str(self.seen_jobs_path)

    def _load(self) -> dict[str, Any]:
        if not self.seen_jobs_path.exists():
            return {"version": 1, "jobs": {}}
        try:
            return json.loads(self.seen_jobs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "jobs": {}}

    def _save(self, payload: dict[str, Any]) -> None:
        temp_path = self.seen_jobs_path.with_suffix(self.seen_jobs_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self.seen_jobs_path)

    def get_seen_fingerprints(self, fingerprints: list[str]) -> set[str]:
        jobs = self._load().get("jobs", {})
        return {fingerprint for fingerprint in fingerprints if fingerprint in jobs}

    def mark_jobs_seen(self, recommendations: list[Recommendation], channels: list[str]) -> None:
        payload = self._load()
        jobs = payload.setdefault("jobs", {})
        now = utc_now().isoformat()
        channel_summary = ",".join(channels)
        for recommendation in recommendations:
            jobs[recommendation.job.fingerprint] = {
                "title": recommendation.job.title,
                "company": recommendation.job.company,
                "url": recommendation.job.url,
                "location": recommendation.job.location,
                "source": recommendation.job.source,
                "score": recommendation.total_score,
                "summary": recommendation.summary,
                "sent_at": now,
                "channels": channel_summary,
            }
        self._save(payload)

    def list_seen_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        jobs = list(self._load().get("jobs", {}).values())
        jobs.sort(key=lambda item: item.get("sent_at", ""), reverse=True)
        return jobs[:limit]


class VercelBlobSeenJobsStore(SeenJobsStore):
    def __init__(self, blob_path: str) -> None:
        self.blob_path = blob_path

    @property
    def location_label(self) -> str:
        return f"vercel-blob:{self.blob_path}"

    def _load(self) -> dict[str, Any]:
        try:
            from vercel.blob import get
        except ImportError as error:
            raise RuntimeError("vercel package is required for seen_store='vercel_blob'") from error

        try:
            result = get(self.blob_path, access="private")
        except Exception:
            return {"version": 1, "jobs": {}}

        if not result or getattr(result, "stream", None) is None:
            return {"version": 1, "jobs": {}}

        raw = result.stream.read()
        if not raw:
            return {"version": 1, "jobs": {}}
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"version": 1, "jobs": {}}

    def _save(self, payload: dict[str, Any]) -> None:
        try:
            from vercel.blob import put
        except ImportError as error:
            raise RuntimeError("vercel package is required for seen_store='vercel_blob'") from error

        content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        put(
            self.blob_path,
            content,
            access="private",
            content_type="application/json",
            add_random_suffix=False,
            overwrite=True,
        )

    def get_seen_fingerprints(self, fingerprints: list[str]) -> set[str]:
        jobs = self._load().get("jobs", {})
        return {fingerprint for fingerprint in fingerprints if fingerprint in jobs}

    def mark_jobs_seen(self, recommendations: list[Recommendation], channels: list[str]) -> None:
        payload = self._load()
        jobs = payload.setdefault("jobs", {})
        now = utc_now().isoformat()
        channel_summary = ",".join(channels)
        for recommendation in recommendations:
            jobs[recommendation.job.fingerprint] = {
                "title": recommendation.job.title,
                "company": recommendation.job.company,
                "url": recommendation.job.url,
                "location": recommendation.job.location,
                "source": recommendation.job.source,
                "score": recommendation.total_score,
                "summary": recommendation.summary,
                "sent_at": now,
                "channels": channel_summary,
            }
        self._save(payload)

    def list_seen_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        jobs = list(self._load().get("jobs", {}).values())
        jobs.sort(key=lambda item: item.get("sent_at", ""), reverse=True)
        return jobs[:limit]


def create_seen_jobs_store(config: AppConfig) -> SeenJobsStore:
    if config.seen_store == "vercel_blob":
        return VercelBlobSeenJobsStore(config.seen_jobs_blob_path)
    return LocalJSONSeenJobsStore(config.seen_jobs_path)
