from __future__ import annotations

from urllib.parse import urlencode

from job_finder.models import Job
from job_finder.sources.base import JobSource
from job_finder.utils import fetch_json, normalize_whitespace


class SerpApiGoogleJobsSource(JobSource):
    BASE_URL = "https://serpapi.com/search"

    def fetch_jobs(self) -> list[Job]:
        import os

        api_key_env = str(self.config.settings.get("api_key_env", "SERPAPI_API_KEY"))
        api_key = os.getenv(api_key_env, "")
        if not api_key:
            raise RuntimeError(f"Missing SerpApi key in environment variable: {api_key_env}")

        query = str(self.config.settings["q"])
        params = {
            "engine": "google_jobs",
            "q": query,
            "api_key": api_key,
        }
        optional_keys = ["location", "gl", "hl", "google_domain", "lrad", "ltype", "chips"]
        for key in optional_keys:
            value = self.config.settings.get(key)
            if value not in (None, ""):
                params[key] = str(value)

        quality = float(self.config.settings.get("quality", 0.8))
        results: list[Job] = []
        next_page_token = None

        while len(results) < self.max_jobs:
            request_params = dict(params)
            if next_page_token:
                request_params["next_page_token"] = next_page_token
            payload = fetch_json(f"{self.BASE_URL}?{urlencode(request_params)}")

            jobs_results = payload.get("jobs_results", [])
            if not jobs_results:
                break

            for entry in jobs_results:
                apply_options = entry.get("apply_options") or []
                first_apply = apply_options[0] if apply_options else {}
                detected = entry.get("detected_extensions") or {}
                location = entry.get("location", "") or ""
                description = entry.get("description", "") or ""
                job_url = first_apply.get("link") or entry.get("share_link") or ""
                if not job_url:
                    continue

                results.append(
                    Job(
                        source=self.config.name,
                        external_id=str(entry.get("job_id") or job_url),
                        title=normalize_whitespace(entry.get("title", "")),
                        company=normalize_whitespace(entry.get("company_name", "")),
                        url=job_url,
                        location=normalize_whitespace(location),
                        description=normalize_whitespace(description),
                        remote=bool(detected.get("work_from_home")) or "remote" in f"{location} {description}".lower(),
                        metadata={
                            "via": entry.get("via", ""),
                            "source_quality": quality,
                            "schedule_type": detected.get("schedule_type", ""),
                            "posted_at_text": detected.get("posted_at", ""),
                            "share_link": entry.get("share_link", ""),
                        },
                    )
                )
                if len(results) >= self.max_jobs:
                    break

            if len(results) >= self.max_jobs:
                break
            next_page_token = ((payload.get("serpapi_pagination") or {}).get("next_page_token"))
            if not next_page_token:
                break

        deduped: dict[str, Job] = {}
        for job in results:
            deduped[job.fingerprint] = job
        return list(deduped.values())
