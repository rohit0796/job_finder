from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from job_finder.models import Job
from job_finder.sources.base import JobSource
from job_finder.utils import fetch_text, html_to_text, normalize_whitespace, parse_datetime

RSS_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _guess_company(title: str) -> str:
    for separator in (" at ", " @ ", " - "):
        if separator in title.lower():
            left, right = re.split(separator, title, maxsplit=1, flags=re.IGNORECASE)
            return normalize_whitespace(right)
    return "Unknown"


class RSSSource(JobSource):
    def fetch_jobs(self) -> list[Job]:
        url = str(self.config.settings["url"])
        xml_text = fetch_text(url)
        root = ET.fromstring(xml_text)

        items = root.findall(".//item")
        atom_entries = root.findall(".//atom:entry", RSS_NS)
        results: list[Job] = []

        if items:
            for item in items[: self.max_jobs]:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                description = html_to_text(item.findtext("description", default="") or "")
                guid = item.findtext("guid", default=link or title)
                pub_date = item.findtext("pubDate")
                company = str(self.config.settings.get("company", _guess_company(title)))
                results.append(
                    Job(
                        source=self.config.name,
                        external_id=guid,
                        title=title,
                        company=company,
                        url=link,
                        description=description,
                        posted_at=parse_datetime(pub_date),
                        remote="remote" in description.lower() or "remote" in title.lower(),
                        metadata={"source_quality": float(self.config.settings.get("quality", 0.65))},
                    )
                )
            return results

        for entry in atom_entries[: self.max_jobs]:
            title = entry.findtext("atom:title", default="", namespaces=RSS_NS).strip()
            description = html_to_text(entry.findtext("atom:summary", default="", namespaces=RSS_NS) or "")
            link_node = entry.find("atom:link", RSS_NS)
            link = link_node.attrib.get("href", "") if link_node is not None else ""
            guid = entry.findtext("atom:id", default=link or title, namespaces=RSS_NS)
            updated = entry.findtext("atom:updated", default="", namespaces=RSS_NS)
            company = str(self.config.settings.get("company", _guess_company(title)))
            results.append(
                Job(
                    source=self.config.name,
                    external_id=guid,
                    title=title,
                    company=company,
                    url=link,
                    description=description,
                    posted_at=parse_datetime(updated),
                    remote="remote" in description.lower() or "remote" in title.lower(),
                    metadata={"source_quality": float(self.config.settings.get("quality", 0.65))},
                )
            )

        return results
