"""J. Who should we actually be predicting?

The walk-forward harness puts the model only 0.052 mean absolute error ahead of a simple average,
well short of the 0.15 the research paper set as the bar. Before reaching for a better model, this
asks a cheaper question: is the margin being diluted by players nobody needs a projection for?

A deep bench receiver who scores near zero every week is trivially predictable, so the model and the
baseline both do well and the gap between them shrinks. The players a reader actually cares about
are the ones with a real role. This measures the margin by how much a player is used, then tests
whether restricting the published population clears the gate.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from common import ROOT, save

from nfl_pipeline.predict.backtest import walk_forward
from nfl_pipeline.predict.features import load_features
from nfl_pipeline.predict.models import baseline_predictions

THRESHOLDS = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)


def margin_by_usage(features: pd.DataFrame) -> dict:
    """Where does the model beat the baseline, and by how much, split by recent scoring level?"""
    result = walk_forward(features, test_seasons=(2024, 2025))
    graded = result.predictions.merge(
        features[["player_id", "season", "week", "ppr_mean5", "position_group"]],
        on=["player_id", "season", "week", "position_group"],
        how="left",
    )
    baselines = baseline_predictions(
        features.set_index(["player_id", "season", "week"])
        .loc[pd.MultiIndex.from_frame(graded[["player_id", "season", "week"]])]
        .reset_index()
    )
    graded["baseline"] = baselines["last_ten"]
    graded["model_error"] = (graded.actual_ppr - graded.points).abs()
    graded["baseline_error"] = (graded.actual_ppr - graded.baseline).abs()

    graded["tier"] = pd.cut(
        graded.ppr_mean5,
        [-0.01, 2, 4, 6, 9, 13, 100],
        labels=["0-2", "2-4", "4-6", "6-9", "9-13", "13+"],
    )
    by_tier = (
        graded.groupby("tier", observed=True)
        .agg(
            player_games=("model_error", "size"),
            mean_actual=("actual_ppr", "mean"),
            model_mae=("model_error", "mean"),
            baseline_mae=("baseline_error", "mean"),
        )
        .assign(margin=lambda d: d.baseline_mae - d.model_mae)
        .round(3)
    )
    by_position = (
        graded.groupby("position_group")
        .agg(
            player_games=("model_error", "size"),
            model_mae=("model_error", "mean"),
            baseline_mae=("baseline_error", "mean"),
        )
        .assign(margin=lambda d: d.baseline_mae - d.model_mae)
        .round(3)
    )
    return {
        "overall": result.summary(),
        "by_recent_scoring_tier": by_tier.reset_index().to_dict("records"),
        "by_position": by_position.reset_index().to_dict("records"),
    }


def margin_by_threshold(features: pd.DataFrame) -> dict:
    """Run the whole harness again for each candidate cut-off, and see which clears the bar."""
    out = {}
    for threshold in THRESHOLDS:
        eligible = features[features.ppr_mean5.fillna(0) >= threshold]
        try:
            result = walk_forward(eligible, test_seasons=(2024, 2025))
        except ValueError:
            continue
        summary = result.summary()
        out[f"ppr_mean5_at_least_{threshold:g}"] = {
            "player_games": summary["player_games"],
            "mae": summary["mae"],
            "best_baseline_mae": summary["baselines"][summary["best_baseline"]],
            "margin": summary["improvement_over_best_baseline"],
            "coverage": summary["interval_coverage"],
            "spearman": summary["spearman"],
            "clears_the_0_15_bar": summary["improvement_over_best_baseline"] >= 0.15,
        }
    return out


def main() -> None:
    features = load_features(Path(ROOT) / "data" / "warehouse.duckdb")
    result = {
        "usage": margin_by_usage(features),
        "thresholds": margin_by_threshold(features),
    }
    save("j_population", result)

    print("Margin over the baseline, by how much a player has been scoring:")
    print(f"  {'tier':>6s} {'games':>7s} {'actual':>7s} {'model':>7s} {'base':>7s} {'margin':>7s}")
    for row in result["usage"]["by_recent_scoring_tier"]:
        print(
            f"  {row['tier']:>6s} {row['player_games']:>7d} {row['mean_actual']:>7.2f} "
            f"{row['model_mae']:>7.3f} {row['baseline_mae']:>7.3f} {row['margin']:>+7.3f}"
        )
    print("\nBy position:")
    for row in result["usage"]["by_position"]:
        print(
            f"  {row['position_group']:>3s} {row['player_games']:>7d} "
            f"model {row['model_mae']:.3f}  base {row['baseline_mae']:.3f}  margin {row['margin']:+.3f}"
        )
    print("\nWhole harness re-run at each cut-off:")
    for name, row in result["thresholds"].items():
        flag = "CLEARS" if row["clears_the_0_15_bar"] else ""
        print(
            f"  {name:>26s} games {row['player_games']:>6d}  mae {row['mae']:.3f}  "
            f"base {row['best_baseline_mae']:.3f}  margin {row['margin']:+.3f}  "
            f"coverage {row['coverage']:.3f} {flag}"
        )


if __name__ == "__main__":
    main()
