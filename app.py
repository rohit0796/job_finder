from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException

from api.cron_run import _resolve_config_path
from job_finder.config import load_config
from job_finder.pipeline import JobFinderPipeline

app = FastAPI()


@app.get("/")
def health() -> dict:
    return {"ok": True, "service": "job-finder"}


@app.get("/api/cron_run")
@app.post("/api/cron_run")
def cron_run(authorization: str | None = Header(default=None)) -> dict:
    import os

    cron_secret = os.getenv("CRON_SECRET", "")
    if cron_secret and authorization != f"Bearer {cron_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    config = load_config(_resolve_config_path())
    pipeline = JobFinderPipeline(config)
    jobs, reports = pipeline.fetch()
    recommendations = pipeline.rank(jobs)
    notification_result = pipeline.notify(recommendations, dry_run=False)
    return {
        "ok": True,
        "fetched_jobs": len(jobs),
        "sources": [
            {
                "name": report.source_name,
                "fetched_jobs": report.fetched_jobs,
                "error": report.error,
            }
            for report in reports
        ],
        "accepted_jobs": notification_result.accepted_jobs,
        "new_jobs": notification_result.new_jobs,
        "skipped_seen_jobs": notification_result.skipped_seen_jobs,
        "notified_jobs": notification_result.notified_jobs,
        "channels_sent": notification_result.channels_sent,
        "errors": notification_result.errors,
        "seen_store": pipeline.store.location_label,
    }
