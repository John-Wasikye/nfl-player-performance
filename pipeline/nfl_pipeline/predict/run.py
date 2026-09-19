"""Tie the prediction engine together: project the coming week, grade the finished ones, publish.

The order here matters and is not arbitrary. Grading happens against the *locked* file, read back
from disk, before anything new is written. If the new projections were generated first and grading
read from memory, a change to the model would quietly rewrite history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from nfl_pipeline.config import Settings
from nfl_pipeline.contract import (
    SCHEMA_VERSION,
    AccuracyFile,
    GradedWeek,
    LedgerFile,
    PredictedPlayer,
    PredictionsFile,
)
from nfl_pipeline.predict.features import POSITIONS, load_features
from nfl_pipeline.predict.ledger import Ledger
from nfl_pipeline.predict.report import build_accuracy_file
from nfl_pipeline.predict.weekly import grade_week, load_locked, lock_week, predict_week
from nfl_pipeline.storage import Storage

logger = logging.getLogger("nfl_pipeline.predict.run")

PREDICTION_PREFIX = "published/v1/predictions"
ACCURACY_PREFIX = "published/v1/accuracy"
LEDGER_KEY = "published/v1/ledger.json"


class PredictionError(Exception):
    """Something was wrong enough that nothing should be published."""


@dataclass
class PredictionSummary:
    season: int
    predicted_week: int | None
    players_predicted: int
    locked: bool
    weeks_graded: int
    files_written: int = 0
    notes: list[str] = field(default_factory=list)


def next_week_to_predict(features: pd.DataFrame, season: int) -> int | None:
    """The earliest week of the season that has fixtures but no results yet.

    Using "earliest unplayed" rather than "latest played plus one" means a week that is partly
    finished is still the week being projected, which is what a reader visiting mid-week wants.
    """
    season_rows = features[features.season == season]
    unplayed = season_rows[season_rows.actual_ppr.isna()]
    if unplayed.empty:
        return None
    return int(unplayed.week.min())


def _player_details(warehouse: Path) -> pd.DataFrame:
    connection = duckdb.connect(str(warehouse), read_only=True)
    try:
        return connection.sql("select player_id, display_name from dim_player").df()
    finally:
        connection.close()


def _to_published(
    rows: pd.DataFrame,
    features: pd.DataFrame,
    names: pd.DataFrame,
    status: str,
    locked_at: str | None,
) -> pd.DataFrame:
    """Join the numbers to the names, teams and fixtures a reader needs to make sense of them."""
    context = features[
        ["player_id", "season", "week", "team", "opponent_team", "is_home", "injury_status"]
    ]
    joined = rows.merge(context, on=["player_id", "season", "week"], how="left").merge(
        names, on="player_id", how="left"
    )
    joined["display_name"] = joined.display_name.fillna(joined.player_id)
    joined["status"] = status
    joined["locked_at"] = locked_at
    return joined


def _write(storage: Storage, key: str, payload) -> None:
    storage.put_bytes(key, payload.model_dump_json(indent=2).encode("utf-8"))


def publish_predictions(
    storage: Storage,
    published: pd.DataFrame,
    *,
    season: int,
    week: int,
    model_version: str,
    now: datetime,
) -> int:
    """One file per position, so the site fetches only what a page needs."""
    written = 0
    for position in POSITIONS:
        rows = published[published.position_group == position]
        if rows.empty:
            continue
        players = [
            PredictedPlayer(
                player_id=row.player_id,
                name=row.display_name,
                team=row.team or "",
                opponent=row.opponent_team or "",
                is_home=bool(row.is_home),
                position=position,
                points=round(float(row.points), 2),
                low=round(float(row.low), 2),
                high=round(float(row.high), 2),
                probability_of_playing=round(float(row.probability_of_playing), 3),
                expected_points=round(float(row.expected_points), 2),
                injury_status=row.injury_status if isinstance(row.injury_status, str) else None,
                status=row.status,
                locked_at=row.locked_at,
            )
            for row in rows.sort_values("expected_points", ascending=False).itertuples()
        ]
        _write(
            storage,
            f"{PREDICTION_PREFIX}/{season}/{week}/{position}.json",
            PredictionsFile(
                schema_version=SCHEMA_VERSION,
                season=season,
                week=week,
                position=position,
                generated_at=now.isoformat(timespec="seconds"),
                model_version=model_version,
                players=players,
            ),
        )
        written += 1
    return written


def grade_finished_weeks(
    features: pd.DataFrame, predictions_dir: Path, season: int
) -> list[GradedWeek]:
    """Grade every locked week that now has results, reading each one back from disk."""
    graded: list[GradedWeek] = []
    for week in sorted(features[features.season == season].week.unique()):
        locked = load_locked(predictions_dir, season, int(week))
        if locked is None or locked.locked_at is None:
            continue
        result = grade_week(locked, features)
        if result is not None:
            graded.append(result)
    return graded


def run_predictions(
    settings: Settings,
    storage: Storage,
    *,
    now: datetime,
    season: int | None = None,
    week: int | None = None,
    lock: bool = False,
) -> PredictionSummary:
    warehouse = Path(settings.warehouse_path)
    if not warehouse.exists():
        raise PredictionError(f"warehouse not found: {warehouse} (run the dbt build first)")
    try:
        features = load_features(warehouse)
    except duckdb.Error as error:
        raise PredictionError(f"could not read the feature store: {error}") from error
    if features.empty:
        raise PredictionError("the feature store is empty")

    season = season or int(features.season.max())
    predictions_dir = Path(settings.predictions_dir)

    # Grade first, from the locked files, before anything new is written.
    graded = grade_finished_weeks(features, predictions_dir, season)
    summary = PredictionSummary(
        season=season,
        predicted_week=None,
        players_predicted=0,
        locked=False,
        weeks_graded=len(graded),
    )

    target = week if week is not None else next_week_to_predict(features, season)
    if target is None:
        summary.notes.append(f"every week of {season} has been played; nothing left to project")
    else:
        try:
            predictions = predict_week(features, season, target)
        except ValueError as error:
            raise PredictionError(f"could not project {season} week {target}: {error}") from error
        if lock:
            predictions = lock_week(predictions, predictions_dir)
        published = _to_published(
            predictions.rows,
            features,
            _player_details(warehouse),
            status=predictions.status,
            locked_at=predictions.locked_at,
        )
        summary.predicted_week = target
        summary.players_predicted = len(published)
        summary.locked = predictions.locked_at is not None
        summary.files_written += publish_predictions(
            storage,
            published,
            season=season,
            week=target,
            model_version=predictions.model_version,
            now=now,
        )

    accuracy: AccuracyFile = build_accuracy_file(season, graded)
    _write(storage, f"{ACCURACY_PREFIX}/{season}.json", accuracy)
    summary.files_written += 1

    ledger = Ledger.load(Path(settings.ledger_path))
    _write(
        storage,
        LEDGER_KEY,
        LedgerFile(
            schema_version=SCHEMA_VERSION,
            generated_at=now.isoformat(timespec="seconds"),
            entries=ledger.entries,
        ),
    )
    summary.files_written += 1
    logger.info(
        "predictions: season %s, week %s, %d players, %d weeks graded, %d files",
        season,
        summary.predicted_week,
        summary.players_predicted,
        summary.weeks_graded,
        summary.files_written,
    )
    return summary
