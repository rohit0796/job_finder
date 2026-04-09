import unittest
from pathlib import Path

from job_finder.config import load_config
from job_finder.models import Job
from job_finder.scoring import JobMatcher


class JobMatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        config_path = Path(__file__).resolve().parents[1] / "job_finder.example.toml"
        self.config = load_config(config_path)
        self.config.groq.enabled = False
        self.matcher = JobMatcher(
            config=self.config,
            resume_text="Python backend engineer with SQL, API design, Docker, AWS, and LLM app experience.",
        )

    def test_prefers_matching_jobs(self) -> None:
        matching_job = Job(
            source="greenhouse",
            external_id="1",
            title="Backend Python Engineer",
            company="Good Co",
            url="https://example.com/1",
            location="Remote",
            description="Build Python APIs with SQL and Docker. 3+ years experience. Remote role.",
            remote=True,
            metadata={"source_quality": 0.9},
        )
        weak_job = Job(
            source="rss",
            external_id="2",
            title="Sales Manager",
            company="Other Co",
            url="https://example.com/2",
            location="Onsite",
            description="Enterprise sales role focused on quotas and outbound motion.",
            remote=False,
            metadata={"source_quality": 0.5},
        )

        high = self.matcher.evaluate(matching_job)
        low = self.matcher.evaluate(weak_job)

        self.assertGreater(high.total_score, low.total_score)
        self.assertTrue(high.accepted)
        self.assertFalse(low.accepted)


if __name__ == "__main__":
    unittest.main()
