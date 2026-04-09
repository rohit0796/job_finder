from __future__ import annotations

from abc import ABC, abstractmethod

from job_finder.config import SourceConfig
from job_finder.models import Job


class JobSource(ABC):
    def __init__(self, config: SourceConfig, max_jobs: int) -> None:
        self.config = config
        self.max_jobs = max_jobs

    @abstractmethod
    def fetch_jobs(self) -> list[Job]:
        raise NotImplementedError
