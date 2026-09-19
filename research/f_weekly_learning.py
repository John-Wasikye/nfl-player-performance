"""F. Does the system actually get smarter week by week? (a falsifiable test of the learning claim)

Four strategies are run through 2024-2025 in true walk-forward order. Each week, only games before
that week exist.

  frozen            one model trained on 2021-2023 and never touched again
  retrain           retrained every week on everything that has happened so far
  retrain+bias      retrain, plus a per-position correction learned from the last 4 weeks of errors
  adaptive          retrain+bias, with ensemble weights that follow each member's recent accuracy

If "the AI gets smarter every week" is real, the later strategies beat `frozen`, and the gap grows.
We also separate two different things that both look like learning:
  (1) the MODEL learning from more data (compare strategies in the same week), and
  (2) the model knowing more about each PLAYER as their season accumulates (MAE by week of season).
"""

from __future__ import annotations

import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from common import connect, save
from d_context_ablation import FEATURES, build_dataset
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

COLS = [c for g in FEATURES.values() for c in g]
PARAMS = dict(
    objective="regression",
    learning_rate=0.03,
    num_leaves=15,
    min_data_in_leaf=60,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbose=-1,
    seed=7,
)
BIAS_WINDOW = 4  # weeks of past errors used for the per-position correction
WEIGHT_WINDOW = 6  # weeks used to score ensemble members
POS = ["QB", "RB", "WR", "TE"]


def fit(train: pd.DataFrame):
    """Fit both ensemble members on the data available so far."""
    x, y = train[COLS].astype(float), train.ppr
    med = x.median()
    gbm = lgb.train(PARAMS, lgb.Dataset(x.fillna(med), y), num_boost_round=400)
    ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))).fit(
        x.fillna(med), y
    )
    return gbm, ridge, med


def predict(models, week_df: pd.DataFrame) -> dict[str, np.ndarray]:
    gbm, ridge, med = models
    x = week_df[COLS].astype(float).fillna(med)
    return {
        "gbm": gbm.predict(x),
        "ridge": ridge.predict(x),
        "naive": week_df["ewm"].fillna(week_df["mean10"]).fillna(week_df["mean5"]).values,
    }


def run(df: pd.DataFrame) -> dict:
    df = df.sort_values(["season", "week"]).reset_index(drop=True)
    test_weeks = [(s, w) for s in (2024, 2025) for w in sorted(df[df.season == s].week.unique())]

    frozen_models = fit(df[df.season <= 2023])
    history: list[pd.DataFrame] = []  # graded past weeks, for bias and weights
    rows = []

    for season, week in test_weeks:
        week_df = df[(df.season == season) & (df.week == week)]
        if len(week_df) < 40:
            continue
        past = df[(df.season < season) | ((df.season == season) & (df.week < week))]

        p_frozen = predict(frozen_models, week_df)["gbm"]
        parts = predict(fit(past), week_df)
        p_retrain = 0.5 * parts["gbm"] + 0.5 * parts["ridge"]

        # --- bias correction: what have we been getting wrong lately, by position?
        bias = {}
        if history:
            recent = pd.concat(history[-BIAS_WINDOW:])
            bias = recent.groupby("pos").apply(lambda g: (g.actual - g.retrain).mean()).to_dict()
        shift = week_df.pos.map(bias).fillna(0.0).values
        p_bias = p_retrain + shift

        # --- adaptive weights: favour whichever member has been closest recently
        if len(history) >= 2:
            recent = pd.concat(history[-WEIGHT_WINDOW:])
            errs = {m: np.abs(recent.actual - recent[m]).mean() for m in ("gbm", "ridge", "naive")}
            inv = {m: 1.0 / max(e, 1e-6) ** 2 for m, e in errs.items()}
            total = sum(inv.values())
            weights = {m: v / total for m, v in inv.items()}
        else:
            weights = {"gbm": 0.5, "ridge": 0.5, "naive": 0.0}
        p_adaptive = sum(weights[m] * parts[m] for m in weights) + shift

        actual = week_df.ppr.values
        rows.append(
            {
                "season": season,
                "week": week,
                "n": len(week_df),
                "frozen": np.abs(actual - p_frozen).mean(),
                "retrain": np.abs(actual - p_retrain).mean(),
                "retrain_bias": np.abs(actual - p_bias).mean(),
                "adaptive": np.abs(actual - p_adaptive).mean(),
                "naive": np.abs(actual - parts["naive"]).mean(),
                "weight_gbm": weights["gbm"],
                "weight_ridge": weights["ridge"],
                "weight_naive": weights["naive"],
            }
        )
        history.append(
            pd.DataFrame(
                {
                    "pos": week_df.pos.values,
                    "actual": actual,
                    "retrain": p_retrain,
                    "gbm": parts["gbm"],
                    "ridge": parts["ridge"],
                    "naive": parts["naive"],
                }
            )
        )

    weekly = pd.DataFrame(rows)
    strategies = ["naive", "frozen", "retrain", "retrain_bias", "adaptive"]

    def weighted(col: str, frame: pd.DataFrame) -> float:
        return float((frame[col] * frame.n).sum() / frame.n.sum())

    overall = {s: weighted(s, weekly) for s in strategies}
    first_half = weekly[weekly.week <= 9]
    second_half = weekly[weekly.week > 9]
    late = weekly.tail(12)

    # Does the retrained model pull away from the frozen one as more data arrives?
    weekly["gap_vs_frozen"] = weekly.frozen - weekly.adaptive
    trend = np.polyfit(np.arange(len(weekly)), weekly.gap_vs_frozen, 1)[0]

    return {
        "weeks_evaluated": int(len(weekly)),
        "player_games": int(weekly.n.sum()),
        "overall_mae": overall,
        "improvement_over_frozen": {s: overall["frozen"] - overall[s] for s in strategies},
        "first_half_of_season_mae": {s: weighted(s, first_half) for s in strategies},
        "second_half_of_season_mae": {s: weighted(s, second_half) for s in strategies},
        "last_12_weeks_mae": {s: weighted(s, late) for s in strategies},
        "gap_vs_frozen_trend_per_week": float(trend),
        "final_ensemble_weights": weekly.iloc[-1][["weight_gbm", "weight_ridge", "weight_naive"]]
        .round(3)
        .to_dict(),
        "weekly": weekly.round(4).to_dict("records"),
    }


def by_week_of_season(weekly_records: list[dict]) -> dict:
    """Separate 'the model learned' from 'we simply know more about each player by week 12'."""
    w = pd.DataFrame(weekly_records)
    bins = {
        "weeks 1-4": (1, 4),
        "weeks 5-9": (5, 9),
        "weeks 10-13": (10, 13),
        "weeks 14+": (14, 30),
    }
    out = {}
    for label, (lo, hi) in bins.items():
        part = w[(w.week >= lo) & (w.week <= hi)]
        if part.empty:
            continue
        out[label] = {
            "player_games": int(part.n.sum()),
            "adaptive_mae": float((part.adaptive * part.n).sum() / part.n.sum()),
            "naive_mae": float((part.naive * part.n).sum() / part.n.sum()),
            "skill_vs_naive": float(((part.naive - part.adaptive) * part.n).sum() / part.n.sum()),
        }
    return out


def main() -> None:
    df = build_dataset(connect())
    result = run(df)
    result["by_week_of_season"] = by_week_of_season(result["weekly"])
    save("f_weekly_learning", result)

    print(f"weeks {result['weeks_evaluated']}, player-games {result['player_games']}\n")
    print("overall MAE (lower is better):")
    for k, v in result["overall_mae"].items():
        print(
            f"  {k:14s} {v:.4f}   improvement vs frozen {result['improvement_over_frozen'][k]:+.4f}"
        )
    print(
        "\nfirst half of season:",
        {k: round(v, 3) for k, v in result["first_half_of_season_mae"].items()},
    )
    print(
        "second half of season:",
        {k: round(v, 3) for k, v in result["second_half_of_season_mae"].items()},
    )
    print("last 12 weeks:", {k: round(v, 3) for k, v in result["last_12_weeks_mae"].items()})
    print(f"\ngap vs frozen, trend per week: {result['gap_vs_frozen_trend_per_week']:+.5f}")
    print("final ensemble weights:", result["final_ensemble_weights"])
    print("\nby week of season:")
    for k, v in result["by_week_of_season"].items():
        print(
            f"  {k:12s} adaptive {v['adaptive_mae']:.3f}  naive {v['naive_mae']:.3f}  skill {v['skill_vs_naive']:+.3f}"
        )


if __name__ == "__main__":
    main()
