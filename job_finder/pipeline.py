from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from job_finder.config import AppConfig, SourceConfig
from job_finder.models import FetchReport, Job, NotificationResult, Recommendation
from job_finder.notifications import EmailNotifier, Notifier, TelegramNotifier
from job_finder.scoring import JobMatcher
from job_finder.sources import BrowserScrapeSource, GreenhouseSource, HTMLScrapeSource, LeverSource, RSSSource, SerpApiGoogleJobsSource
from job_finder.storage import create_seen_jobs_store


def build_source(source_config: SourceConfig, max_jobs: int):
    mapping = {
        "greenhouse": GreenhouseSource,
        "lever": LeverSource,
        "rss": RSSSource,
        "html_scrape": HTMLScrapeSource,
        "browser_scrape": BrowserScrapeSource,
        "serpapi_google_jobs": SerpApiGoogleJobsSource,
    }
    source_cls = mapping.get(source_config.type)
    if not source_cls:
        raise ValueError(f"Unsupported source type: {source_config.type}")
    return source_cls(source_config, max_jobs=max_jobs)


def format_recommendations(recommendations: list[Recommendation]) -> str:
    lines: list[str] = []
    for index, recommendation in enumerate(recommendations, start=1):
        job = recommendation.job
        matched = ", ".join(recommendation.matched_skills[:6]) or "none"
        missing = ", ".join(recommendation.missing_skills[:5]) or "none"
        lines.extend(
            [
                f"{index}. {job.title} at {job.company}",
                f"   score: {recommendation.total_score:.2f} | source: {job.source} | location: {job.location or 'n/a'}",
                f"   matched: {matched}",
                f"   resume gaps: {missing}",
                f"   why: {recommendation.summary}",
                f"   apply: {job.url}",
            ]
        )
    return "\n".join(lines)


class JobFinderPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.store = create_seen_jobs_store(config)
        self.resume_text = config.resume_path.read_text(encoding="utf-8")
        self.matcher = JobMatcher(config=config, resume_text=self.resume_text)

    def fetch(self) -> tuple[list[Job], list[FetchReport]]:
        sources = [build_source(source, self.config.max_jobs_per_source) for source in self.config.sources if source.enabled]
        all_jobs: list[Job] = []
        reports: list[FetchReport] = []
        if not sources:
            return all_jobs, reports

        with ThreadPoolExecutor(max_workers=min(8, len(sources))) as executor:
            future_map = {executor.submit(source.fetch_jobs): source for source in sources}
            for future in as_completed(future_map):
                source = future_map[future]
                try:
                    jobs = future.result()
                    all_jobs.extend(jobs)
                    reports.append(FetchReport(source_name=source.config.name, fetched_jobs=len(jobs)))
                except Exception as error:
                    reports.append(FetchReport(source_name=source.config.name, fetched_jobs=0, error=str(error)))

        deduped = list({job.fingerprint: job for job in all_jobs}.values())
        return deduped, sorted(reports, key=lambda report: report.source_name.lower())

    def rank(self, jobs: list[Job]) -> list[Recommendation]:
        return sorted((self.matcher.evaluate(job) for job in jobs), key=lambda item: item.total_score, reverse=True)[: self.config.top_k]

    def build_notifiers(self) -> list[Notifier]:
        notifiers: list[Notifier] = []
        if self.config.telegram and self.config.telegram.enabled and self.config.telegram.bot_token and self.config.telegram.chat_id:
            notifiers.append(TelegramNotifier(self.config.telegram.bot_token, self.config.telegram.chat_id))
        if self.config.email and self.config.email.enabled and self.config.email.password:
            notifiers.append(
                EmailNotifier(
                    smtp_host=self.config.email.smtp_host,
                    smtp_port=self.config.email.smtp_port,
                    username=self.config.email.username,
                    password=self.config.email.password,
                    from_address=self.config.email.from_address,
                    to_address=self.config.email.to_address,
                    use_ssl=self.config.email.use_ssl,
                )
            )
        return notifiers

    def notify(self, recommendations: list[Recommendation], dry_run: bool = False) -> NotificationResult:
        accepted = [item for item in recommendations if item.accepted]
        if not accepted:
            return NotificationResult(
                accepted_jobs=0,
                new_jobs=0,
                skipped_seen_jobs=0,
                notified_jobs=0,
                channels_sent=[],
            )

        seen = self.store.get_seen_fingerprints([item.job.fingerprint for item in accepted])
        new_jobs = [item for item in accepted if item.job.fingerprint not in seen]
        skipped = len(accepted) - len(new_jobs)

        if dry_run:
            return NotificationResult(
                accepted_jobs=len(accepted),
                new_jobs=len(new_jobs),
                skipped_seen_jobs=skipped,
                notified_jobs=0,
                channels_sent=[],
            )

        if not new_jobs:
            return NotificationResult(
                accepted_jobs=len(accepted),
                new_jobs=0,
                skipped_seen_jobs=skipped,
                notified_jobs=0,
                channels_sent=[],
            )

        notifiers = self.build_notifiers()
        if not notifiers:
            return NotificationResult(
                accepted_jobs=len(accepted),
                new_jobs=len(new_jobs),
                skipped_seen_jobs=skipped,
                notified_jobs=0,
                channels_sent=[],
                errors=["No notification channels configured"],
            )

        message = format_recommendations(new_jobs)
        subject = f"Job Finder: {len(new_jobs)} new shortlisted roles"
        channels_sent: list[str] = []
        errors: list[str] = []
        for notifier in notifiers:
            try:
                notifier.send(subject=subject, message=message)
                channels_sent.append(notifier.name)
            except Exception as error:
                errors.append(f"{notifier.name}: {error}")

        if channels_sent:
            self.store.mark_jobs_seen(new_jobs, channels_sent)

        return NotificationResult(
            accepted_jobs=len(accepted),
            new_jobs=len(new_jobs),
            skipped_seen_jobs=skipped,
            notified_jobs=len(new_jobs) if channels_sent else 0,
            channels_sent=channels_sent,
            errors=errors,
        )
