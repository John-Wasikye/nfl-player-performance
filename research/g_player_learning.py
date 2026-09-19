"""G. Which weekly learning mechanisms actually work?

F showed that retraining the model every week barely helps (the training set hardly changes). This
tests mechanisms that learn about *individual players and situations* instead, which is what "gets
smarter every week" ought to mean in practice. Walk-forward through 2024-2025.

  base            retrained ensemble, no adjustment                       (the F baseline)
  player_bias     + each player's own recent over/under-performance, shrunk toward zero
  role_change     + extra weight on the last 2 games when a player's usage has clearly shifted
  both            player_bias + role_change
  oracle_shrunk   an upper bound: the player's true season-long bias, shrunk (not achievable live)
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
# A player's bias is only trusted in proportion to how many games it rests on:
# weight = games / (games + K). K = 8 means 8 games buys half credit.
SHRINK_K = 8.0
MIN_GAMES_FOR_BIAS = 3


def fit(train: pd.DataFrame):
    x, y = train[COLS].astype(float), train.ppr
    med = x.median()
    gbm = lgb.train(PARAMS, lgb.Dataset(x.fillna(med), y), num_boost_round=400)
    ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))).fit(
        x.fillna(med), y
    )
    return gbm, ridge, med


def blend(models, frame: pd.DataFrame) -> np.ndarray:
    gbm, ridge, med = models
    x = frame[COLS].astype(float).fillna(med)
    return 0.5 * gbm.predict(x) + 0.5 * ridge.predict(x)


def run(df: pd.DataFrame) -> dict:
    df = df.sort_values(["season", "week"]).reset_index(drop=True)
    graded: list[pd.DataFrame] = []
    rows = []

    for season in (2024, 2025):
        for week in sorted(df[df.season == season].week.unique()):
            week_df = df[(df.season == season) & (df.week == week)]
            if len(week_df) < 40:
                continue
            past = df[(df.season < season) | ((df.season == season) & (df.week < week))]
            base = blend(fit(past), week_df)

            # --- player bias, learned only from already-graded weeks
            if graded:
                hist = pd.concat(graded)
                stats = hist.groupby("player_id").agg(
                    bias=("error", "mean"),
                    games=("error", "size"),
                    recent=("error", lambda s: s.tail(4).mean()),
                )
                stats["shrunk"] = stats.bias * (stats.games / (stats.games + SHRINK_K))
                stats.loc[stats.games < MIN_GAMES_FOR_BIAS, "shrunk"] = 0.0
                player_shift = week_df.player_id.map(stats.shrunk).fillna(0.0).values
            else:
                player_shift = np.zeros(len(week_df))

            # --- role change: usage in the last 2 games well above or below the last 5
            prior_form = week_df[["mean5", "mean10"]].mean(axis=1)
            shifted = (week_df["mean3"] - week_df["mean10"]).fillna(0.0)
            role_flag = (shifted.abs() > 0.35 * prior_form.clip(lower=1)).values
            role_shift = np.where(role_flag, 0.45 * shifted.values, 0.0)

            actual = week_df.ppr.values
            variants = {
                "base": base,
                "player_bias": base + player_shift,
                "role_change": base + role_shift,
                "both": base + player_shift + role_shift,
            }
            row = {
                "season": season,
                "week": week,
                "n": len(week_df),
                "players_with_bias": int((player_shift != 0).sum()),
                "players_flagged_role_change": int(role_flag.sum()),
            }
            for name, pred in variants.items():
                row[name] = float(np.abs(actual - pred).mean())
            rows.append(row)

            graded.append(
                pd.DataFrame(
                    {
                        "player_id": week_df.player_id.values,
                        "error": actual - base,
                        "season": season,
                        "week": week,
                    }
                )
            )

    weekly = pd.DataFrame(rows)
    names = ["base", "player_bias", "role_change", "both"]

    def w(col, frame=weekly):
        return float((frame[col] * frame.n).sum() / frame.n.sum())

    overall = {n: w(n) for n in names}

    # Upper bound: if we somehow knew each player's true bias for these seasons in advance.
    hist = pd.concat(graded)
    truth = hist.groupby("player_id").agg(bias=("error", "mean"), games=("error", "size"))
    truth["shrunk"] = truth.bias * (truth.games / (truth.games + SHRINK_K))
    oracle_gain = float(
        np.abs(hist.error).mean()
        - np.abs(hist.error - hist.player_id.map(truth.shrunk).fillna(0.0)).mean()
    )

    second_half = weekly[weekly.week > 9]
    return {
        "weeks": int(len(weekly)),
        "player_games": int(weekly.n.sum()),
        "overall_mae": overall,
        "improvement_over_base": {n: overall["base"] - overall[n] for n in names},
        "second_half_mae": {n: w(n, second_half) for n in names},
        "mean_players_with_learned_bias_per_week": float(weekly.players_with_bias.mean()),
        "mean_players_flagged_role_change_per_week": float(
            weekly.players_flagged_role_change.mean()
        ),
        "oracle_player_bias_gain_upper_bound": oracle_gain,
        "weekly": weekly.round(4).to_dict("records"),
    }


def main() -> None:
    result = run(build_dataset(connect()))
    save("g_player_learning", result)
    print(f"weeks {result['weeks']}, player-games {result['player_games']}\n")
    for k, v in result["overall_mae"].items():
        print(f"  {k:14s} MAE {v:.4f}   vs base {result['improvement_over_base'][k]:+.4f}")
    print(
        "\nsecond half of season:", {k: round(v, 3) for k, v in result["second_half_mae"].items()}
    )
    print(
        f"players with a learned bias per week: {result['mean_players_with_learned_bias_per_week']:.0f}"
    )
    print(
        f"players flagged as role change per week: {result['mean_players_flagged_role_change_per_week']:.0f}"
    )
    print(
        f"\nORACLE upper bound for player-bias learning: {result['oracle_player_bias_gain_upper_bound']:+.4f} MAE"
    )


if __name__ == "__main__":
    main()
