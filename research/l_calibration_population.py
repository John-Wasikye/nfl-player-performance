"""L. Does calibrating on the published population fix the coverage drop?

Experiment K found that training on everyone and publishing only players with a real role gives the
best point accuracy (margin +0.170 against +0.159) but drags interval coverage from 0.798 down to
0.778, against a nominal 0.80.

That is not noise, and it has a name. Split conformal prediction only guarantees coverage when the
calibration set is exchangeable with what is being predicted. Low-volume players have small errors
because near-zero scores are easy, so calibrating on a population full of them produces a correction
that is too small for the players actually published.

The fix follows from the theory rather than from a search: train on everything, calibrate on the
population that will be published. This checks whether coverage comes back without giving up the
point accuracy that training wide bought.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from common import ROOT, save
from scipy import stats

from nfl_pipeline.predict.backtest import walk_forward
from nfl_pipeline.predict.features import load_features
from nfl_pipeline.predict.models import MIN_RECENT_SCORING, PredictionModel, baseline_predictions

TEST_SEASONS = (2024, 2025)


class CalibrateOnEveryone(PredictionModel):
    """The old behaviour, kept only so the two can be compared in one run."""

    def _calibrate(self, calibration: pd.DataFrame) -> float:  # noqa: D102
        usable = self.trainable(calibration)
        if len(usable) < 100:
            return 0.0
        x = self._prepare(usable)
        low, high = self._low.predict(x), self._high.predict(x)
        actual = usable.actual_ppr.to_numpy()
        import numpy as np

        from nfl_pipeline.predict.models import NOMINAL_COVERAGE

        miss = np.maximum(low - actual, actual - high)
        return float(np.quantile(miss, min(0.999, NOMINAL_COVERAGE * (1 + 1 / len(miss)))))


def score_on_publishable(features: pd.DataFrame, model_factory) -> dict:
    """Train on the whole population, then grade only the players that would be published."""
    result = walk_forward(features, test_seasons=TEST_SEASONS, model_factory=model_factory)
    graded = result.predictions.merge(
        features[["player_id", "season", "week", "ppr_mean5", "ppr_mean10", "ppr_season_avg"]],
        on=["player_id", "season", "week"],
        how="left",
    )
    graded = graded[graded.ppr_mean5.fillna(0) >= MIN_RECENT_SCORING]

    baselines = baseline_predictions(graded)
    mae = float((graded.actual_ppr - graded.points).abs().mean())
    baseline_maes = {
        name: float((graded.actual_ppr - values).abs().mean()) for name, values in baselines.items()
    }
    best = min(baseline_maes, key=baseline_maes.get)
    return {
        "player_games": len(graded),
        "mae": round(mae, 4),
        "best_baseline_mae": round(baseline_maes[best], 4),
        "margin": round(baseline_maes[best] - mae, 4),
        "interval_coverage": round(
            float(((graded.actual_ppr >= graded.low) & (graded.actual_ppr <= graded.high)).mean()),
            4,
        ),
        "mean_interval_width": round(float((graded.high - graded.low).mean()), 3),
        "spearman": round(float(stats.spearmanr(graded.actual_ppr, graded.points).statistic), 4),
    }


def main() -> None:
    features = load_features(Path(ROOT) / "data" / "warehouse.duckdb")
    everyone = score_on_publishable(features, CalibrateOnEveryone)
    publishable = score_on_publishable(features, PredictionModel)

    in_band = 0.78 <= publishable["interval_coverage"] <= 0.82
    save(
        "l_calibration_population",
        {
            "threshold": MIN_RECENT_SCORING,
            "calibrated_on_everyone": everyone,
            "calibrated_on_publishable": publishable,
            "coverage_back_in_the_78_82_band": in_band,
        },
    )

    print(f"Trained on everyone, graded on players with ppr_mean5 >= {MIN_RECENT_SCORING:g}:\n")
    header = f"  {'calibrated on':>22s} {'mae':>7s} {'margin':>8s} {'coverage':>9s} {'width':>7s}"
    print(header)
    for name, row in (("everyone", everyone), ("the published population", publishable)):
        print(
            f"  {name:>22s} {row['mae']:>7.4f} {row['margin']:>+8.4f} "
            f"{row['interval_coverage']:>9.3f} {row['mean_interval_width']:>7.2f}"
        )
    print(
        f"\nCoverage is {'back inside' if in_band else 'still outside'} the 78-82% band "
        f"the paper requires."
    )


if __name__ == "__main__":
    main()
