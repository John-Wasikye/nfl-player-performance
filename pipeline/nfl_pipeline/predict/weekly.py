"""The weekly cycle: predict, lock, grade.

The locking step is the reason any of the published accuracy can be believed. A projection is
written to disk before the games are played and then never rewritten. Grading reads that file back.
Without the lock, nothing stops a later pipeline run from quietly regenerating last week's
predictions with a better model and reporting the improved number as if it had been made in
advance, and the Report card would measure nothing at all.

So `lock_week` refuses to overwrite. If the stored file disagrees with what is being written, that
is an error to investigate, not something to paper over.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from nfl_pipeline.contract import GradedWeek
from nfl_pipeline.predict.availability import AvailabilityModel
from nfl_pipeline.predict.backtest import _split_for_calibration
from nfl_pipeline.predict.models import PredictionModel, baseline_predictions

logger = logging.getLogger("nfl_pipeline.predict.weekly")

# Columns stored in the lock file. Deliberately no player name or team: those live in the marts and
# can be corrected later, while a locked projection must never change.
LOCKED_COLUMNS = [
    "player_id",
    "season",
    "week",
    "position_group",
    "points",
    "low",
    "high",
    "probability_of_playing",
    "expected_points",
    "model_version",
]

MIN_HISTORY_ROWS = 2000


@dataclass
class WeeklyPredictions:
    """One week's projections, before or after they were locked."""

    season: int
    week: int
    generated_at: str
    model_version: str
    rows: pd.DataFrame
    locked_at: str | None = None

    @property
    def status(self) -> str:
        return "locked" if self.locked_at else "preliminary"

    def to_json(self) -> dict:
        return {
            "season": self.season,
            "week": self.week,
            "generated_at": self.generated_at,
            "locked_at": self.locked_at,
            "model_version": self.model_version,
            "rows": self.rows[LOCKED_COLUMNS].round(6).to_dict("records"),
        }

    @classmethod
    def from_json(cls, payload: dict) -> WeeklyPredictions:
        return cls(
            season=payload["season"],
            week=payload["week"],
            generated_at=payload["generated_at"],
            locked_at=payload.get("locked_at"),
            model_version=payload["model_version"],
            rows=pd.DataFrame(payload["rows"], columns=LOCKED_COLUMNS),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def predict_week(
    features: pd.DataFrame,
    season: int,
    week: int,
    model_factory=PredictionModel,
) -> WeeklyPredictions:
    """Project one week, training only on games that had finished before it.

    The history filter is the same one the backtest uses, so a projection made live is produced by
    exactly the process the Report card was validated with.
    """
    history = features[
        (features.season < season) | ((features.season == season) & (features.week < week))
    ]
    trainable = PredictionModel.trainable(history)
    if len(trainable) < MIN_HISTORY_ROWS:
        raise ValueError(
            f"only {len(trainable)} usable rows before {season} week {week}; "
            f"need {MIN_HISTORY_ROWS} to predict"
        )

    current = features[(features.season == season) & (features.week == week)]
    current = PredictionModel.predictable(current)
    if current.empty:
        raise ValueError(f"no player in {season} week {week} has enough history to project")

    train, calibration = _split_for_calibration(trainable)
    model = model_factory().fit(train, calibration=calibration)

    availability = AvailabilityModel()
    questionable = trainable[trainable.injury_status == "Questionable"]
    if len(questionable):
        availability.fit(questionable, (questionable.actual_ppr > 0).astype(int))
    probability = availability.probability_of_playing(current)

    rows = model.predict(current, play_probability=probability.to_numpy())
    # Anyone ruled out is dropped rather than shown at zero: a projection of zero reads like a
    # prediction of a bad game, when what we mean is that he is not playing.
    rows = rows[rows.probability_of_playing > 0]
    return WeeklyPredictions(
        season=season,
        week=week,
        generated_at=_now(),
        model_version=model.version,
        rows=rows.reset_index(drop=True),
    )


def lock_path(root: Path, season: int, week: int) -> Path:
    return Path(root) / str(season) / f"week_{week:02d}.json"


def lock_week(predictions: WeeklyPredictions, root: Path) -> WeeklyPredictions:
    """Write the week's projections once, before kickoff, and never again.

    Re-locking with identical numbers is allowed because pipeline runs are retried; re-locking with
    different numbers raises, because that is either a bug or the report card being rewritten after
    the fact, and both need a human.
    """
    path = lock_path(root, predictions.season, predictions.week)
    locked = WeeklyPredictions(
        season=predictions.season,
        week=predictions.week,
        generated_at=predictions.generated_at,
        model_version=predictions.model_version,
        rows=predictions.rows,
        locked_at=_now(),
    )
    if path.exists():
        existing = WeeklyPredictions.from_json(json.loads(path.read_text("utf-8")))
        if _same_numbers(existing.rows, locked.rows):
            logger.info("week %s already locked, numbers unchanged", predictions.week)
            return existing
        raise ValueError(
            f"{path} is already locked with different projections. A locked week cannot be "
            "rewritten; if the earlier lock was wrong, delete it deliberately and say so in the "
            "ledger."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(locked.to_json(), indent=2), encoding="utf-8")
    logger.info(
        "locked %d projections for %s week %s", len(locked.rows), locked.season, locked.week
    )
    return locked


def _same_numbers(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    key = ["player_id", "season", "week"]
    a = left[LOCKED_COLUMNS].sort_values(key).reset_index(drop=True).round(6)
    b = right[LOCKED_COLUMNS].sort_values(key).reset_index(drop=True).round(6)
    return a.equals(b)


def load_locked(root: Path, season: int, week: int) -> WeeklyPredictions | None:
    path = lock_path(root, season, week)
    if not path.exists():
        return None
    return WeeklyPredictions.from_json(json.loads(path.read_text("utf-8")))


def grade_week(
    locked: WeeklyPredictions,
    features: pd.DataFrame,
    frozen_points: pd.Series | None = None,
) -> GradedWeek | None:
    """Score a locked week against what actually happened.

    Only players who played are graded. Someone who was projected and then did not appear is not a
    miss by the points model; that is the availability model's business and is measured separately.

    `frozen_points` is the control: a model fixed before the season, graded on the same rows. If the
    current model is not beating it, the engine has not improved, whatever else has changed.
    """
    actual = features[(features.season == locked.season) & (features.week == locked.week)][
        ["player_id", "actual_ppr", "ppr_mean5", "ppr_mean10", "ppr_season_avg"]
    ]
    graded = locked.rows.merge(actual, on="player_id", how="inner")
    graded = graded[graded.actual_ppr.notna()]
    if graded.empty:
        return None

    error = (graded.actual_ppr - graded.points).to_numpy()
    baselines = baseline_predictions(graded)
    frozen_mae = None
    if frozen_points is not None:
        aligned = frozen_points.reindex(graded.player_id.to_numpy())
        if aligned.notna().all():
            frozen_mae = round(float(np.mean(np.abs(graded.actual_ppr - aligned.to_numpy()))), 4)

    return GradedWeek(
        season=locked.season,
        week=locked.week,
        player_games=len(graded),
        mae=round(float(np.mean(np.abs(error))), 4),
        rmse=round(float(np.sqrt(np.mean(error**2))), 4),
        interval_coverage=round(
            float(np.mean((graded.actual_ppr >= graded.low) & (graded.actual_ppr <= graded.high))),
            4,
        ),
        baseline_mae={
            name: round(float(np.mean(np.abs(graded.actual_ppr - values))), 4)
            for name, values in baselines.items()
        },
        frozen_model_mae=frozen_mae,
    )
