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

from nfl_pipeline.predict.models import (
    MIN_RECENT_SCORING,
    PredictionModel,
    baseline_predictions,
)

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
                current[
                    # `ppr_mean5` is carried so the published population can be identified after
                    # the replay, without re-reading the feature store.
                    ["player_id", "season", "week", "position_group", "actual_ppr", "ppr_mean5"]
                ].assign(points=points, low=low, high=high)
            )

    if not result.weeks:
        raise ValueError("no week had enough history and players to evaluate")
    result.predictions = pd.concat(graded, ignore_index=True)
    return result


def promotion_decision(
    champion: BacktestResult,
    challenger: BacktestResult,
    margin: float = PROMOTION_MARGIN,
    paired: dict | None = None,
) -> dict:
    """Should the challenger replace the champion?

    Only if it is better by more than the noise margin. A tie keeps the incumbent, which is what
    makes the published accuracy a ratchet rather than a random walk.
    """
    improvement = champion.mae - challenger.mae
    coverage_ok = 0.75 <= challenger.coverage <= 0.85
    # When the paired evidence is available it has to agree. An improvement smaller than about two
    # of its own standard errors is not distinguishable from chance however large the margin looks,
    # and the fixed margin alone cannot tell the difference.
    consistent = paired is None or abs(paired["standard_errors_from_zero"]) >= 2.0
    promote = improvement > margin and coverage_ok and consistent
    if promote:
        reason = f"beats the champion by {improvement:.3f} mean absolute error"
    elif improvement > margin and coverage_ok and not consistent:
        reason = (
            f"{improvement:.3f} better, but only "
            f"{paired['standard_errors_from_zero']:.1f} standard errors from zero across "
            f"{paired['player_games']:,} player-games, so it is not distinguishable from chance"
        )
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
        "paired": paired,
    }


@dataclass
class PublishedScore:
    """A replay's accuracy over the players the site actually shows.

    The harness trains and replays over everyone, which is right: throwing away training data made
    the model worse (research section 5.15). But the product is judged on the roughly two thirds of
    players with a real enough role to be published, and a change should be judged the same way.
    Scoring a candidate over the whole population dilutes it — an idea that helps exactly the
    players on the site and does nothing for a deep-bench receiver would look two thirds as good as
    it is.

    Duck-typed to what `promotion_decision` reads, so it can be passed in place of a raw result.
    """

    mae: float
    coverage: float
    player_games: int
    predictions: pd.DataFrame


def score_on_published(result: BacktestResult) -> PublishedScore:
    """Re-score a completed replay over the published population only."""
    rows = result.predictions
    published = rows[rows.ppr_mean5.fillna(0) >= MIN_RECENT_SCORING]
    if published.empty:
        raise ValueError("no graded rows survived the published-population filter")
    actual = published.actual_ppr.to_numpy()
    return PublishedScore(
        mae=float(np.mean(np.abs(actual - published.points.to_numpy()))),
        coverage=float(np.mean((actual >= published.low) & (actual <= published.high))),
        player_games=len(published),
        predictions=published,
    )


def paired_evidence(champion: PublishedScore, challenger: PublishedScore) -> dict:
    """How consistent the improvement is, using the fact that both saw identical rows.

    Comparing two mean absolute errors throws that away. The same player-week appears on both
    sides, so the difference can be taken per row, and the spread of those differences says
    directly whether an improvement is distinguishable from noise — something a fixed margin can
    only approximate.

    The mean of the paired differences equals the difference of the two MAEs exactly, so this adds
    a standard error to a number the gate already uses rather than replacing it.
    """
    key = ["player_id", "season", "week"]
    merged = champion.predictions[[*key, "actual_ppr", "points"]].merge(
        challenger.predictions[[*key, "points"]], on=key, suffixes=("_champion", "_challenger")
    )
    if merged.empty:
        raise ValueError("champion and challenger share no graded rows, so they cannot be compared")

    actual = merged.actual_ppr.to_numpy()
    # Positive means the challenger was closer on that row.
    difference = np.abs(actual - merged.points_champion.to_numpy()) - np.abs(
        actual - merged.points_challenger.to_numpy()
    )
    mean = float(np.mean(difference))
    standard_error = float(np.std(difference, ddof=1) / np.sqrt(len(difference)))
    return {
        "player_games": len(difference),
        "mean_improvement": round(mean, 4),
        "standard_error": round(standard_error, 4),
        # How many times the mean improvement is its own standard error. Under 2 is not
        # distinguishable from chance at the usual threshold.
        "standard_errors_from_zero": round(mean / standard_error, 2) if standard_error else 0.0,
        "rows_improved": int(np.sum(difference > 0)),
    }
