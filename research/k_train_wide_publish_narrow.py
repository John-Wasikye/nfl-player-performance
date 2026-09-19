"""K. Should low-volume players be dropped from training too, or only from publishing?

Experiment J found the model only earns its keep on players with a real role, and that restricting
to `ppr_mean5 >= 4` clears the promotion bar. But J filtered the data before the harness saw it,
which dropped those players from training as well as from grading. Those are different claims:

  - "nobody needs a projection for a deep-bench player" is a product decision, and a defensible one
  - "the model learns worse when it also sees deep-bench players" is an empirical claim, untested

They point opposite ways. More training data usually helps, so if low-volume rows are harmless to
learn from we should keep them and only restrict what gets published. If they actively hurt (the
model spends its capacity fitting an easy near-zero regime), dropping them twice is right.

This runs both and compares on the same graded rows, so the difference is the only thing that moves.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from common import ROOT, save

from nfl_pipeline.predict.backtest import walk_forward
from nfl_pipeline.predict.features import load_features

PUBLISH_THRESHOLD = 4.0
TEST_SEASONS = (2024, 2025)


def _eligible(frame: pd.DataFrame) -> pd.Series:
    return frame.ppr_mean5.fillna(0) >= PUBLISH_THRESHOLD


def train_narrow(features: pd.DataFrame) -> dict:
    """What J measured: low-volume players dropped from training and from grading."""
    result = walk_forward(features[_eligible(features)], test_seasons=TEST_SEASONS)
    return result.summary()


def train_wide(features: pd.DataFrame) -> dict:
    """Train on everyone, then grade only the players who would actually be published.

    The harness grades whatever it is given, so the restriction is applied afterwards by re-scoring
    its output on the eligible rows only.
    """
    result = walk_forward(features, test_seasons=TEST_SEASONS)
    graded = result.predictions.merge(
        features[["player_id", "season", "week", "ppr_mean5", "ppr_mean10", "ppr_season_avg"]],
        on=["player_id", "season", "week"],
        how="left",
    )
    graded = graded[_eligible(graded)]

    from nfl_pipeline.predict.models import baseline_predictions

    baselines = baseline_predictions(graded)
    mae = float((graded.actual_ppr - graded.points).abs().mean())
    baseline_maes = {
        name: float((graded.actual_ppr - values).abs().mean()) for name, values in baselines.items()
    }
    best = min(baseline_maes, key=baseline_maes.get)
    from scipy import stats

    return {
        "player_games": len(graded),
        "mae": round(mae, 4),
        "baselines": {k: round(v, 4) for k, v in baseline_maes.items()},
        "best_baseline": best,
        "improvement_over_best_baseline": round(baseline_maes[best] - mae, 4),
        "interval_coverage": round(
            float(((graded.actual_ppr >= graded.low) & (graded.actual_ppr <= graded.high)).mean()),
            4,
        ),
        "spearman": round(float(stats.spearmanr(graded.actual_ppr, graded.points).statistic), 4),
    }


def main() -> None:
    features = load_features(Path(ROOT) / "data" / "warehouse.duckdb")
    narrow = train_narrow(features)
    wide = train_wide(features)
    verdict = (
        "train on everyone, publish only the eligible"
        if wide["improvement_over_best_baseline"] > narrow["improvement_over_best_baseline"]
        else "drop low-volume players from training as well"
    )
    save(
        "k_train_wide_publish_narrow",
        {"threshold": PUBLISH_THRESHOLD, "narrow": narrow, "wide": wide, "verdict": verdict},
    )

    print(f"Graded on players with ppr_mean5 >= {PUBLISH_THRESHOLD:g}, both ways:\n")
    for name, row in (("trained narrow", narrow), ("trained wide", wide)):
        print(
            f"  {name:>15s}  games {row['player_games']:>6d}  mae {row['mae']:.4f}  "
            f"base {row['baselines'][row['best_baseline']]:.4f}  "
            f"margin {row['improvement_over_best_baseline']:+.4f}  "
            f"coverage {row['interval_coverage']:.3f}  spearman {row['spearman']:.4f}"
        )
    print(f"\nVerdict: {verdict}")


if __name__ == "__main__":
    main()
