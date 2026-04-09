import tempfile
import unittest
from pathlib import Path

from job_finder.models import Job, Recommendation
from job_finder.storage import LocalJSONSeenJobsStore


class LocalSeenJobsStoreTests(unittest.TestCase):
    def test_marks_and_lists_seen_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalJSONSeenJobsStore(Path(temp_dir) / "seen_jobs.json")
            recommendation = Recommendation(
                job=Job(
                    source="serpapi",
                    external_id="1",
                    title="Python Engineer",
                    company="Example Co",
                    url="https://example.com/job",
                ),
                total_score=0.9,
                accepted=True,
                breakdown={"semantic": 0.9},
                matched_skills=["python"],
                missing_skills=[],
                summary="good fit",
            )

            self.assertEqual(store.get_seen_fingerprints([recommendation.job.fingerprint]), set())
            store.mark_jobs_seen([recommendation], ["telegram"])
            self.assertEqual(store.get_seen_fingerprints([recommendation.job.fingerprint]), {recommendation.job.fingerprint})

            rows = store.list_seen_jobs(limit=5)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Python Engineer")
            self.assertEqual(rows[0]["channels"], "telegram")


if __name__ == "__main__":
    unittest.main()
