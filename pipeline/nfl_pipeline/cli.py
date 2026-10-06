"""Command line entry point.

nfl-pipeline ingest      download nflverse files into raw storage
nfl-pipeline publish     validate the rankings and write the published JSON
nfl-pipeline predict     project the coming week, grade the finished ones, publish both
nfl-pipeline experiment  report where the model missed, or put one candidate through the gate
nfl-pipeline backtest    score the rankings against what happened the following week
nfl-pipeline run         ingest, then dbt build (models and tests), then publish
nfl-pipeline daily       run, then project the coming week and lock it when its window opens
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import httpx

from nfl_pipeline.backtest import render_report, run_backtest
from nfl_pipeline.config import (
    Settings,
    build_records_storage,
    build_site_storage,
    build_storage,
    dbt_raw_root,
    dbt_target,
)
from nfl_pipeline.datasets import DATASETS, resolve_files
from nfl_pipeline.ingest import ingest
from nfl_pipeline.predict.experiment import (
    ExperimentError,
    list_candidates,
    run_candidate,
    write_report,
)
from nfl_pipeline.predict.run import PredictionError, run_predictions
from nfl_pipeline.publish import PublishError, publish
from nfl_pipeline.season import current_season, parse_seasons
from nfl_pipeline.snapshot import SnapshotError, ensure_warehouse, publish_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nfl-pipeline", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def add_ingest_options(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--seasons",
            help='seasons to ingest, e.g. "2026", "2024,2025" or "2021-2026" '
            "(default: current season)",
        )
        command.add_argument(
            "--datasets",
            help=f"comma-separated datasets (default: all). Known: {', '.join(DATASETS)}",
        )
        command.add_argument(
            "--force", action="store_true", help="download even if the source has not changed"
        )

    add_ingest_options(
        commands.add_parser("ingest", help="download nflverse files into raw storage")
    )
    commands.add_parser("publish", help="validate the rankings and write the published JSON")
    predict = commands.add_parser(
        "predict", help="project the coming week, grade the finished ones, publish both"
    )
    predict.add_argument("--season", type=int, help="season to work on (default: the latest)")
    predict.add_argument(
        "--week", type=int, help="week to project (default: the earliest one not yet played)"
    )
    predict.add_argument(
        "--lock",
        action="store_true",
        help="write the projections to disk as final. Only do this before the first kickoff of "
        "the week: a locked week cannot be rewritten, which is what makes the Report card honest.",
    )
    predict.add_argument(
        "--lock-when-due",
        action="store_true",
        help="the unattended form of --lock: lock only if the week's first kickoff is within 24 "
        "hours and more than 30 minutes away, publish an existing lock instead of recomputing it, "
        "and refuse (exit 1) if the kickoff has passed with the week unlocked.",
    )
    experiment = commands.add_parser(
        "experiment",
        help="the weekly learning loop: report where the model missed, or test one candidate",
    )
    experiment.add_argument(
        "--run",
        metavar="NAME",
        help="evaluate a registered candidate feature and record the verdict in the ledger",
    )
    experiment.add_argument("--list", action="store_true", help="list the registered candidates")
    experiment.add_argument(
        "--report",
        default="docs/last-week.md",
        help="where to write the failure report (default: docs/last-week.md)",
    )
    backtest = commands.add_parser(
        "backtest", help="score the rankings against what happened the following week"
    )
    backtest.add_argument(
        "--report", default="docs/backtest.md", help="where to write the Markdown report"
    )
    add_ingest_options(
        commands.add_parser("run", help="ingest, build the dbt models and tests, then publish")
    )
    add_ingest_options(
        commands.add_parser(
            "daily",
            help="run, then project the coming week and lock it if its kickoff window has opened",
        )
    )
    return parser


def _run_ingest(args: argparse.Namespace, settings: Settings, now: datetime) -> int:
    try:
        seasons = parse_seasons(args.seasons) if args.seasons else [current_season(now.date())]
        names = [name.strip() for name in args.datasets.split(",")] if args.datasets else None
        files = resolve_files(names, seasons)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

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


def _run_dbt_build(settings: Settings) -> int:
    """Run `dbt build` (seeds, models, and data quality tests) against the local raw files."""
    env = {
        **os.environ,
        "RAW_ROOT": dbt_raw_root(settings),
        "S3_ENDPOINT_URL": settings.s3_endpoint_url or "",
        "WAREHOUSE_PATH": str(settings.warehouse_path),
    }
    command = [
        sys.executable,
        "-c",
        "import sys; from dbt.cli.main import cli; sys.exit(cli())",
        "build",
        "--project-dir",
        str(settings.dbt_dir),
        "--profiles-dir",
        str(settings.dbt_dir),
        "--target",
        dbt_target(settings),
    ]
    return subprocess.run(command, env=env).returncode


def _have_warehouse(settings: Settings) -> bool:
    """On AWS a task starts with an empty disk: use the snapshot, else rebuild from raw.

    Locally the warehouse is whatever `run` last built, so nothing is fetched and a missing file is
    reported by the command that needed it.
    """
    if settings.storage_backend == "local":
        return True
    return ensure_warehouse(
        Path(settings.warehouse_path),
        build_storage(settings),
        lambda: _run_dbt_build(settings) == 0,
    )


def _run_publish(settings: Settings, now: datetime) -> int:
    if not _have_warehouse(settings):
        print("publish failed: no warehouse snapshot and the rebuild failed", file=sys.stderr)
        return 1
    try:
        summary = publish(settings.warehouse_path, build_site_storage(settings), now=now)
    except PublishError as error:
        print(f"publish failed: {error}", file=sys.stderr)
        return 1
    print(
        f"published season {summary.season} through week {summary.latest_week} "
        f"({summary.files_written} files)"
    )
    return 0


def _run_predict(args: argparse.Namespace, settings: Settings, now: datetime) -> int:
    if not _have_warehouse(settings):
        print("predict failed: no warehouse snapshot and the rebuild failed", file=sys.stderr)
        return 1
    try:
        summary = run_predictions(
            settings,
            build_site_storage(settings),
            records=build_records_storage(settings),
            now=now,
            season=args.season,
            week=args.week,
            lock=args.lock,
            lock_when_due=getattr(args, "lock_when_due", False),
        )
    except PredictionError as error:
        print(f"predict failed: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        # Raised when a locked week would have been overwritten. That needs a person, not a retry.
        print(f"predict refused: {error}", file=sys.stderr)
        return 1

    if summary.predicted_week is None:
        print(f"nothing to project for {summary.season}: {'; '.join(summary.notes)}")
    else:
        state = "locked" if summary.locked else "preliminary"
        print(
            f"projected {summary.players_predicted} players for {summary.season} "
            f"week {summary.predicted_week} ({state})"
        )
    print(f"graded {summary.weeks_graded} finished weeks; wrote {summary.files_written} files")
    return 0


def _run_experiment(args: argparse.Namespace, settings: Settings, now: datetime) -> int:
    if args.list:
        for name, hypothesis in list_candidates():
            print(f"{name}")
            print(f"    {hypothesis}")
            print()
        return 0

    if not _have_warehouse(settings):
        print("experiment failed: no warehouse snapshot and the rebuild failed", file=sys.stderr)
        return 1

    try:
        if args.run:
            result = run_candidate(
                Path(settings.warehouse_path),
                build_records_storage(settings),
                args.run,
                now,
                settings.ledger_key,
            )
            verdict = "PROMOTED" if result.promoted else "REJECTED"
            print(f"{result.name}: {verdict} - {result.reason}")
            print(
                f"  champion {result.champion_mae:.4f}  challenger {result.challenger_mae:.4f}  "
                f"coverage {result.challenger_coverage:.3f}"
            )
            print(f"  recorded as {result.entry_id}")
            return 0

        report = write_report(Path(settings.warehouse_path), Path(args.report))
    except ExperimentError as error:
        print(f"experiment failed: {error}", file=sys.stderr)
        return 1

    print(
        f"wrote {report.path}: {report.season} week {report.week}, "
        f"{report.player_games} player-games"
    )
    print(
        f"  average error {report.mae:.3f} against {report.baseline_mae:.3f} for the best baseline"
    )
    return 0


def _run_backtest(args: argparse.Namespace, settings: Settings, now: datetime) -> int:
    if not _have_warehouse(settings):
        print("backtest failed: no warehouse snapshot and the rebuild failed", file=sys.stderr)
        return 1
    try:
        summary = run_backtest(settings.warehouse_path, now=now)
    except (ValueError, OSError) as error:
        print(f"backtest failed: {error}", file=sys.stderr)
        return 1
    except duckdb.Error as error:
        print(f"backtest failed: could not read the warehouse ({error})", file=sys.stderr)
        return 1
    build_storage(settings).put_bytes(
        "backtest/summary.json", json.dumps(summary, indent=2).encode("utf-8")
    )
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(summary), encoding="utf-8")
    print(
        f"backtest done: chose {summary['selected_efficiency_weight']:.0%} efficiency "
        f"(current setting {summary['current_efficiency_weight']:.0%}); report at {report}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # httpx logs every request URL at INFO, and GitHub's download redirects carry signed tokens.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    now = datetime.now(timezone.utc)
    settings = Settings.from_env()

    if args.command == "ingest":
        return _run_ingest(args, settings, now)
    if args.command == "publish":
        return _run_publish(settings, now)
    if args.command == "predict":
        return _run_predict(args, settings, now)
    if args.command == "experiment":
        return _run_experiment(args, settings, now)
    if args.command == "backtest":
        return _run_backtest(args, settings, now)

    if args.command == "daily":
        # Predictions are only made from a warehouse this same run just built and validated: locking
        # from a stale one would freeze a forecast made from old data.
        code = _run_pipeline(args, settings, now)
        if code != 0:
            print("daily stopped: the run failed, so no projections were made", file=sys.stderr)
            return code
        args.season = None
        args.week = None
        args.lock = False
        args.lock_when_due = True
        return _run_predict(args, settings, now)

    return _run_pipeline(args, settings, now)


def _run_pipeline(args: argparse.Namespace, settings: Settings, now: datetime) -> int:
    # "run": each step must succeed before the next one starts, so bad data is never published.
    code = _run_ingest(args, settings, now)
    if code != 0:
        print("run stopped: the ingest failed", file=sys.stderr)
        return code
    if _run_dbt_build(settings) != 0:
        print("run stopped: dbt build failed, so nothing was published", file=sys.stderr)
        return 1

    # The snapshot is for the ad-hoc tasks, not for the site, so a failed upload must not hold back
    # fresh rankings. It must not pass quietly either: publish first, then exit non-zero.
    snapshot_failed = False
    if settings.storage_backend != "local":
        try:
            publish_snapshot(Path(settings.warehouse_path), build_storage(settings))
        except SnapshotError as error:
            print(f"run: {error}", file=sys.stderr)
            snapshot_failed = True
    code = _run_publish(settings, now)
    if code == 0 and snapshot_failed:
        print("run finished, but the snapshot upload failed (see above)", file=sys.stderr)
        return 1
    return code
