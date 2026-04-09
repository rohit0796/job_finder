from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from job_finder.config import load_config
from job_finder.pipeline import JobFinderPipeline


def _resolve_config_path() -> Path:
    env_path = os.getenv("JOB_FINDER_CONFIG_PATH", "").strip()
    if env_path:
        return Path(env_path)
    vercel_path = Path("job_finder.vercel.toml")
    if vercel_path.exists():
        return vercel_path
    return Path("job_finder.toml")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        auth_header = self.headers.get("authorization", "")
        cron_secret = os.getenv("CRON_SECRET", "")
        if cron_secret and auth_header != f"Bearer {cron_secret}":
            self._send_json(401, {"ok": False, "error": "Unauthorized"})
            return

        try:
            config = load_config(_resolve_config_path())
            pipeline = JobFinderPipeline(config)
            jobs, reports = pipeline.fetch()
            recommendations = pipeline.rank(jobs)
            notification_result = pipeline.notify(recommendations, dry_run=False)
            payload = {
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
            status = 200 if not notification_result.errors else 207
            self._send_json(status, payload)
        except Exception as error:
            self._send_json(500, {"ok": False, "error": str(error)})

    def do_POST(self):
        self.do_GET()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
