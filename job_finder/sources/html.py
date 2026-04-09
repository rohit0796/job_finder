from __future__ import annotations

from urllib.parse import urljoin

from job_finder.models import Job
from job_finder.sources.base import JobSource
from job_finder.utils import fetch_text, normalize_whitespace


class HTMLScrapeSource(JobSource):
    def fetch_jobs(self) -> list[Job]:
        try:
            from bs4 import BeautifulSoup
        except ImportError as error:
            raise RuntimeError("beautifulsoup4 is required for html_scrape sources") from error

        search_url = str(self.config.settings["search_url"])
        item_selector = str(self.config.settings["item_selector"])
        title_selector = str(self.config.settings["title_selector"])
        company_selector = str(self.config.settings.get("company_selector", ""))
        location_selector = str(self.config.settings.get("location_selector", ""))
        link_selector = str(self.config.settings["link_selector"])
        description_selector = str(self.config.settings.get("description_selector", ""))
        detail_description_selector = str(self.config.settings.get("detail_description_selector", ""))
        quality = float(self.config.settings.get("quality", 0.7))
        limit = min(int(self.config.settings.get("limit", self.max_jobs)), self.max_jobs)

        html = fetch_text(search_url)
        soup = BeautifulSoup(html, "html.parser")
        results: list[Job] = []

        for item in soup.select(item_selector)[:limit]:
            title = self._safe_text(item, title_selector)
            company = self._safe_text(item, company_selector) if company_selector else ""
            location = self._safe_text(item, location_selector) if location_selector else ""
            url = self._safe_attr(item, link_selector, "href")
            url = urljoin(search_url, url) if url else ""
            description = self._safe_text(item, description_selector) if description_selector else ""

            if detail_description_selector and url:
                try:
                    detail_html = fetch_text(url)
                    detail_soup = BeautifulSoup(detail_html, "html.parser")
                    description = self._safe_text(detail_soup, detail_description_selector) or description
                except Exception:
                    pass

            if not title or not url:
                continue

            lower_text = f"{location} {description}".lower()
            results.append(
                Job(
                    source=self.config.name,
                    external_id=url,
                    title=normalize_whitespace(title),
                    company=normalize_whitespace(company) or self.config.name,
                    url=url,
                    location=normalize_whitespace(location),
                    description=normalize_whitespace(description),
                    remote="remote" in lower_text or "work from home" in lower_text,
                    metadata={"source_quality": quality},
                )
            )

        return results

    def _safe_text(self, scope, selector: str) -> str:
        if not selector:
            return ""
        try:
            node = scope.select_one(selector)
            return normalize_whitespace(node.get_text(" ", strip=True) if node else "")
        except Exception:
            return ""

    def _safe_attr(self, scope, selector: str, attribute: str) -> str:
        try:
            node = scope.select_one(selector)
            value = node.get(attribute, "") if node else ""
            return normalize_whitespace(value)
        except Exception:
            return ""
