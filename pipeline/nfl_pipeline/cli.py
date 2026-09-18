"""Command line entry point: `nfl-pipeline ingest`."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import datetime, timezone

import httpx

from nfl_pipeline.config import Settings, build_storage
from nfl_pipeline.datasets import DATASETS, resolve_files
from nfl_pipeline.ingest import ingest
from nfl_pipeline.season import current_season, parse_seasons


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nfl-pipeline", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    ingest_parser = commands.add_parser("ingest", help="download nflverse files into raw storage")
    ingest_parser.add_argument(
        "--seasons",
        help='seasons to ingest, e.g. "2026", "2024,2025" or "2021-2026" (default: current season)',
    )
    ingest_parser.add_argument(
        "--datasets",
        help=f"comma-separated datasets (default: all). Known: {', '.join(DATASETS)}",
    )
    ingest_parser.add_argument(
        "--force", action="store_true", help="download even if the source has not changed"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs every request URL at INFO, and GitHub's download redirects carry signed tokens.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    now = datetime.now(timezone.utc)
    try:
        seasons = parse_seasons(args.seasons) if args.seasons else [current_season(now.date())]
        names = [name.strip() for name in args.datasets.split(",")] if args.datasets else None
        files = resolve_files(names, seasons)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    settings = Settings.from_env()
    storage = build_storage(settings)
    with httpx.Client(timeout=settings.http_timeout, follow_redirects=True) as client:
        manifest = ingest(
            files,
            storage,
            client,
            now=now,
            force=args.force,
            max_attempts=settings.max_attempts,
        )

    summary = ", ".join(f"{count} {status}" for status, count in sorted(manifest.counts().items()))
    print(f"run {manifest.run_id}: {summary}")
    for result in manifest.failed:
        print(f"  FAILED {result.dataset}/{result.filename}: {result.error}", file=sys.stderr)
    return 1 if manifest.failed else 0
