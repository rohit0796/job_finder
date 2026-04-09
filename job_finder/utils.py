from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

DEFAULT_TIMEOUT = 25
DEFAULT_HEADERS = {
    "User-Agent": "job-finder-agent/0.1 (+local-cli)",
    "Accept": "*/*",
}


class MLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_data(self) -> str:
        return " ".join(self._chunks)


def html_to_text(value: str) -> str:
    stripper = MLStripper()
    stripper.feed(value or "")
    return normalize_whitespace(stripper.get_data())


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="replace")


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT, headers: dict[str, str] | None = None) -> Any:
    return json.loads(fetch_text(url, timeout=timeout, headers=headers))


def safe_fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT, headers: dict[str, str] | None = None) -> str | None:
    try:
        return fetch_text(url, timeout=timeout, headers=headers)
    except urllib.error.URLError:
        return None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        return datetime.fromisoformat(candidate)
    except ValueError:
        pass
    for pattern in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(candidate, pattern)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
