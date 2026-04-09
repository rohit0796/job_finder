from __future__ import annotations

import argparse
from pathlib import Path

from job_finder.config import DEFAULT_CONFIG_PATH, load_config, write_example_config
from job_finder.pipeline import JobFinderPipeline, format_recommendations
from job_finder.storage import create_seen_jobs_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Personal job hunting agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to TOML config file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-config", help="Write a starter config file")
    init_parser.add_argument("--force", action="store_true", help="Overwrite config if it already exists")

    subparsers.add_parser("fetch", help="Fetch jobs and print source results")

    run_parser = subparsers.add_parser("run", help="Fetch, rank, and optionally notify")
    run_parser.add_argument("--dry-run", action="store_true", help="Do not send notifications or mark jobs as seen")

    list_parser = subparsers.add_parser("list", help="List recently seen jobs")
    list_parser.add_argument("--limit", type=int, default=10, help="How many results to print")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-config":
        if args.config.exists() and not args.force:
            parser.error(f"Config already exists at {args.config}. Use --force to overwrite.")
        written = write_example_config(args.config)
        print(f"Wrote config to {written}")
        return 0

    config = load_config(args.config)
    if not config.resume_path.exists():
        parser.error(f"Resume file not found: {config.resume_path}")

    if args.command == "fetch":
        pipeline = JobFinderPipeline(config)
        jobs, reports = pipeline.fetch()
        print(f"Fetched {len(jobs)} deduped jobs")
        for report in reports:
            status = f"{report.fetched_jobs} jobs"
            if report.error:
                status += f" | error: {report.error}"
            print(f"- {report.source_name}: {status}")
        print(f"Seen store: {pipeline.store.location_label}")
        return 0

    if args.command == "run":
        pipeline = JobFinderPipeline(config)
        jobs, reports = pipeline.fetch()
        recommendations = pipeline.rank(jobs)
        accepted = [item for item in recommendations if item.accepted]
        print(f"Fetched {len(jobs)} deduped jobs across {len(reports)} sources")
        for report in reports:
            status = f"{report.fetched_jobs} jobs"
            if report.error:
                status += f" | error: {report.error}"
            print(f"- {report.source_name}: {status}")
        print(f"Shortlisted {len(accepted)} of top {len(recommendations)} jobs")
        if recommendations:
            print()
            print(format_recommendations(recommendations))
        notification_result = pipeline.notify(recommendations, dry_run=args.dry_run)
        print()
        print(f"New shortlisted jobs: {notification_result.new_jobs}")
        print(f"Already seen jobs skipped: {notification_result.skipped_seen_jobs}")
        if args.dry_run:
            print("Dry run: no notifications sent and seen store not updated")
        else:
            print(f"Notifications sent via: {', '.join(notification_result.channels_sent) or 'none'}")
            print(f"Jobs marked seen: {notification_result.notified_jobs}")
        if notification_result.errors:
            for error in notification_result.errors:
                print(f"- notify error: {error}")
        print(f"Seen store: {pipeline.store.location_label}")
        return 0

    if args.command == "list":
        store = create_seen_jobs_store(config)
        rows = store.list_seen_jobs(limit=args.limit)
        if not rows:
            print("No seen jobs found")
            return 0
        for index, row in enumerate(rows, start=1):
            print(f"{index}. {row['title']} at {row['company']} | {row.get('score', 0):.2f}")
            print(f"   sent: {row.get('sent_at', 'n/a')} | channels: {row.get('channels', 'n/a')}")
            print(f"   {row.get('url', '')}")
        print(f"Seen store: {store.location_label}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2
