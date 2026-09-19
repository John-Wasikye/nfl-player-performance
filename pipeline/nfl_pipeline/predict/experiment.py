"""The weekly learning loop, as one command's worth of logic.

Two modes, and the split between them is the point. `report` says where the champion missed; that
is evidence. `run` tests one proposed change against the gate; that is a verdict. Nothing in here
lets the two meet: the thing that reads the failures never gets to decide whether its own idea
worked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

from nfl_pipeline.predict.analyze import analyze_week, eligible_for_report
from nfl_pipeline.predict.backtest import walk_forward
from nfl_pipeline.predict.candidates import evaluate
from nfl_pipeline.predict.features import load_features
from nfl_pipeline.predict.ledger import Ledger
from nfl_pipeline.predict.proposals import REGISTRY

logger = logging.getLogger("nfl_pipeline.predict.experiment")


class ExperimentError(Exception):
    """The loop could not run. Nothing is recorded."""


@dataclass
class ReportResult:
    path: Path
    season: int
    week: int
    player_games: int
    mae: float
    baseline_mae: float


@dataclass
class RunResult:
    name: str
    entry_id: str
    promoted: bool
    reason: str
    champion_mae: float
    challenger_mae: float
    challenger_coverage: float


def list_candidates() -> list[tuple[str, str]]:
    return sorted((name, c.hypothesis) for name, c in REGISTRY.items())


def _features(warehouse: Path):
    try:
        return load_features(warehouse)
    except (duckdb.Error, OSError) as error:
        raise ExperimentError(f"could not read the feature store: {error}") from error


def write_report(warehouse: Path, destination: Path) -> ReportResult:
    """Describe the champion's misses on the most recent graded week."""
    features = _features(warehouse)
    graded = features[features.actual_ppr.notna()]
    if graded.empty:
        raise ExperimentError("nothing has been graded yet, so there are no misses to report")
    season = int(graded.season.max())

    try:
        replay = walk_forward(features, test_seasons=(season,))
    except ValueError as error:
        raise ExperimentError(str(error)) from error

    # The week to report on is the last one the replay actually scored, not the last one with any
    # result at all. Early in a season the newest week usually has a single finished game, far too
    # few players to say anything about; reporting on it would dress up noise as a weekly finding.
    week = int(max(w.week for w in replay.weeks))
    rows = eligible_for_report(features, season, week)
    scored = rows.merge(
        replay.predictions[["player_id", "season", "week", "points"]],
        on=["player_id", "season", "week"],
        how="inner",
    )
    if scored.empty:
        raise ExperimentError(f"no graded projections for {season} week {week}")

    connection = duckdb.connect(str(warehouse), read_only=True)
    try:
        names = connection.sql("select player_id, display_name from dim_player").df()
    finally:
        connection.close()

    report = analyze_week(scored, names=names)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report.to_markdown(), encoding="utf-8")
    return ReportResult(
        path=destination,
        season=season,
        week=week,
        player_games=report.player_games,
        mae=report.mae,
        baseline_mae=report.baseline_mae,
    )


def run_candidate(warehouse: Path, ledger_path: Path, name: str, now: datetime) -> RunResult:
    """Put one candidate through the gate and record whatever it says."""
    candidate = REGISTRY.get(name)
    if candidate is None:
        raise ExperimentError(f"no candidate named {name!r}. Known: {', '.join(sorted(REGISTRY))}")

    features = _features(warehouse)
    try:
        result = evaluate(candidate, features)
    except ValueError as error:
        # Refused before scoring: it read the outcome, or changed the rows being compared. A number
        # produced either way would be worse than no number at all.
        raise ExperimentError(f"candidate refused: {error}") from error

    ledger = Ledger.load(ledger_path)
    entry_id = f"{now:%Y-%m-%d}-{candidate.name}"
    try:
        ledger.record(
            entry_id=entry_id,
            hypothesis=candidate.hypothesis,
            change=f"added feature(s) {', '.join(candidate.adds)}",
            decision=result.decision,
        )
    except ValueError as error:
        raise ExperimentError(str(error)) from error
    ledger.save()

    return RunResult(
        name=candidate.name,
        entry_id=entry_id,
        promoted=result.decision["promote"],
        reason=result.decision["reason"],
        champion_mae=result.champion["mae"],
        challenger_mae=result.challenger["mae"],
        challenger_coverage=result.challenger["interval_coverage"],
    )
