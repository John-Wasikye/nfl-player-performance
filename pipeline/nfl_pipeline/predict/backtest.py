"""The walk-forward harness, and the gate that decides whether a change is allowed to ship.

This is the referee. Every model, feature and rule in the prediction engine has to get past it, and
it is the reason the published accuracy can only move one way: a change is adopted only if it beats
the current champion on weeks neither of them was trained on.

The harness replays history one week at a time. For each week it trains only on games that had
already happened, predicts, then grades. That is slower than a single split but it is the only
honest way to answer "how would this have done at the time".
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from nfl_pipeline.predict.models import PredictionModel, baseline_predictions

# A week needs enough players to produce a meaningful weekly score.
MIN_PLAYERS_PER_WEEK = 30
# How much of the training history is held back to calibrate the prediction ranges.
CALIBRATION_FRACTION = 0.2
# A change must beat the champion by more than this to ship. The research measured typical
# week-to-week noise, so anything smaller is indistinguishable from luck.
PROMOTION_MARGIN = 0.05


@dataclass
class WeekResult:
    season: int
    week: int
    players: int
    mae: float
    rmse: float
    coverage: float
    baselines: dict[str, float]


@dataclass
class BacktestResult:
    """Everything the harness learned, plus the graded rows for further analysis."""

    weeks: list[WeekResult] = field(default_factory=list)
    predictions: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def player_games(self) -> int:
        return int(sum(w.players for w in self.weeks))

    def _weighted(self, values: Iterable[float]) -> float:
        weights = np.array([w.players for w in self.weeks], dtype=float)
        return float(np.average(np.array(list(values), dtype=float), weights=weights))

    @property
    def mae(self) -> float:
        return self._weighted(w.mae for w in self.weeks)

    @property
    def rmse(self) -> float:
        return self._weighted(w.rmse for w in self.weeks)

    @property
    def coverage(self) -> float:
        return self._weighted(w.coverage for w in self.weeks)

    def baseline_mae(self, name: str) -> float:
        return self._weighted(w.baselines[name] for w in self.weeks)

    def summary(self) -> dict:
        baselines = {name: self.baseline_mae(name) for name in self.weeks[0].baselines}
        best = min(baselines, key=baselines.get)
        actual = self.predictions.actual_ppr.to_numpy()
        predicted = self.predictions.points.to_numpy()
        return {
            "weeks": len(self.weeks),
            "player_games": self.player_games,
            "mae": round(self.mae, 4),
            "rmse": round(self.rmse, 4),
            "interval_coverage": round(self.coverage, 4),
            "spearman": round(float(stats.spearmanr(actual, predicted).statistic), 4),
            "baselines": {k: round(v, 4) for k, v in baselines.items()},
            "best_baseline": best,
            "improvement_over_best_baseline": round(baselines[best] - self.mae, 4),
        }


def _split_for_calibration(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Hold back the most recent slice of history to calibrate the prediction ranges.

    It has to be the most recent part rather than a random sample, because the ranges should be
    calibrated on data as close as possible to what is about to be predicted.
    """
    if len(history) < 1000:
        return history, None
    ordered = history.sort_values(["season", "week"])
    cut = int(len(ordered) * (1 - CALIBRATION_FRACTION))
    train, calibration = ordered.iloc[:cut], ordered.iloc[cut:]
    # Any player-week that appears in both would invalidate the calibration.
    key = ["player_id", "season", "week"]
    calibration = calibration.merge(
        train[key].drop_duplicates().assign(_seen=1), on=key, how="left"
    )
    calibration = calibration[calibration._seen.isna()].drop(columns="_seen")
    return train, (calibration if len(calibration) >= 100 else None)


def walk_forward(
    features: pd.DataFrame,
    test_seasons: tuple[int, ...],
    model_factory=PredictionModel,
    min_history_rows: int = 2000,
) -> BacktestResult:
    """Replay `test_seasons` a week at a time, training only on what came before each week."""
    result = BacktestResult()
    graded: list[pd.DataFrame] = []

    for season in test_seasons:
        weeks = sorted(features[features.season == season].week.unique())
        for week in weeks:
            current = features[(features.season == season) & (features.week == week)]
            current = PredictionModel.trainable(current)
            if len(current) < MIN_PLAYERS_PER_WEEK:
                continue
            history = features[
                (features.season < season) | ((features.season == season) & (features.week < week))
            ]
            history = PredictionModel.trainable(history)
            if len(history) < min_history_rows:
                continue

            train, calibration = _split_for_calibration(history)
            model = model_factory().fit(train, calibration=calibration)
            points = model.predict_points(current)
            low, high = model.predict_interval(current)
            actual = current.actual_ppr.to_numpy()
            baselines = baseline_predictions(current)

            result.weeks.append(
                WeekResult(
                    season=season,
                    week=int(week),
                    players=len(current),
                    mae=float(np.mean(np.abs(actual - points))),
                    rmse=float(np.sqrt(np.mean((actual - points) ** 2))),
                    coverage=float(np.mean((actual >= low) & (actual <= high))),
                    baselines={
                        name: float(np.mean(np.abs(actual - values)))
                        for name, values in baselines.items()
                    },
                )
            )
            graded.append(
                current[["player_id", "season", "week", "position_group", "actual_ppr"]].assign(
                    points=points, low=low, high=high
                )
            )

    if not result.weeks:
        raise ValueError("no week had enough history and players to evaluate")
    result.predictions = pd.concat(graded, ignore_index=True)
    return result


def promotion_decision(
    champion: BacktestResult, challenger: BacktestResult, margin: float = PROMOTION_MARGIN
) -> dict:
    """Should the challenger replace the champion?

    Only if it is better by more than the noise margin. A tie keeps the incumbent, which is what
    makes the published accuracy a ratchet rather than a random walk.
    """
    improvement = champion.mae - challenger.mae
    coverage_ok = 0.75 <= challenger.coverage <= 0.85
    promote = improvement > margin and coverage_ok
    if promote:
        reason = f"beats the champion by {improvement:.3f} mean absolute error"
    elif not coverage_ok:
        reason = (
            f"interval coverage {challenger.coverage:.3f} is outside the acceptable "
            "0.75-0.85 band, so its ranges would be dishonest"
        )
    elif improvement > 0:
        reason = f"only {improvement:.3f} better, which is within the {margin} noise margin"
    else:
        reason = f"worse than the champion by {-improvement:.3f}"
    return {
        "promote": bool(promote),
        "reason": reason,
        "champion_mae": round(champion.mae, 4),
        "challenger_mae": round(challenger.mae, 4),
        "improvement": round(improvement, 4),
        "challenger_coverage": round(challenger.coverage, 4),
        "margin": margin,
    }
