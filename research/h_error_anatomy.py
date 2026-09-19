"""H. Where does the model fail, and is that failure reachable by anything other than more numbers?

F and G showed that nudging predictions from recent errors does not work. Before concluding that
nothing can be added, this asks a different question: is the error *concentrated* in situations that
can be identified before kickoff? If it is, a layer that understands those situations has something
real to aim at. If the error is spread evenly, no amount of context will help.

Walk-forward 2024-2025, same predictions as F (retrained ensemble).

  1  Concentration: what share of total error comes from the worst few percent of player-games?
  2  Segments: are big misses identifiable in advance (returning from an absence, thin history,
     top teammate out, volatile usage, a new team, an injury designation)?
  3  The prize: how much total error would disappear if each segment were predicted as well as an
     ordinary game? That is the ceiling for any context-aware layer.
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


def walk_forward(df: pd.DataFrame) -> pd.DataFrame:
    """Predict every week of 2024-2025 using only earlier games."""
    out = []
    for season in (2024, 2025):
        for week in sorted(df[df.season == season].week.unique()):
            week_df = df[(df.season == season) & (df.week == week)]
            if len(week_df) < 40:
                continue
            past = df[(df.season < season) | ((df.season == season) & (df.week < week))]
            x, y = past[COLS].astype(float), past.ppr
            med = x.median()
            gbm = lgb.train(PARAMS, lgb.Dataset(x.fillna(med), y), num_boost_round=400)
            ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))).fit(
                x.fillna(med), y
            )
            xt = week_df[COLS].astype(float).fillna(med)
            pred = 0.5 * gbm.predict(xt) + 0.5 * ridge.predict(xt)
            block = week_df.copy()
            block["pred"] = pred
            block["abs_error"] = np.abs(block.ppr - pred)
            out.append(block)
    return pd.concat(out, ignore_index=True)


def add_segments(res: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Flags that would all be known before kickoff."""
    played = df[["player_id", "season", "week"]].assign(played=1)
    res = res.merge(
        played.assign(week=played.week + 1).rename(columns={"played": "played_last_week"}),
        on=["player_id", "season", "week"],
        how="left",
    )
    res["played_last_week"] = res.played_last_week.fillna(0)
    res["returning"] = (res.played_last_week == 0) & (res.prior_games >= 4)

    res["thin_history"] = res.prior_games <= 6
    res["volatile"] = res.std8 > res.std8.quantile(0.75)
    res["usage_shift"] = (res.mean3 - res.mean10).abs() > 0.4 * res.mean10.clip(lower=1)
    res["questionable_flag"] = res.questionable == 1

    prev_team = df.sort_values(["player_id", "season", "week"]).groupby("player_id").team.shift(1)
    team_map = df.assign(prev_team=prev_team).set_index(["player_id", "season", "week"]).prev_team
    res["prev_team"] = res.set_index(["player_id", "season", "week"]).index.map(team_map)
    res["new_team"] = res.prev_team.notna() & (res.prev_team != res.team)

    # Is the team's usual top fantasy option missing this week?
    top = (
        df.sort_values("mean5", ascending=False)
        .groupby(["team", "season", "week"])
        .player_id.first()
        .rename("team_top")
    )
    res = res.join(top, on=["team", "season", "week"])
    present = df.set_index(["player_id", "season", "week"]).index
    res["top_teammate_out"] = [
        (t is not None) and ((t, s, w) not in present)
        for t, s, w in zip(res.team_top, res.season, res.week, strict=True)
    ]
    return res


def main() -> None:
    df = build_dataset(connect())
    res = add_segments(walk_forward(df), df)
    total = res.abs_error.sum()
    mae = res.abs_error.mean()

    # --- 1. concentration
    ranked = res.abs_error.sort_values(ascending=False).values
    concentration = {
        f"worst_{p}pct_of_games": {
            "share_of_total_error": float(ranked[: int(len(ranked) * p / 100)].sum() / total),
            "mean_error_in_group": float(ranked[: int(len(ranked) * p / 100)].mean()),
        }
        for p in (1, 5, 10, 25)
    }

    # --- 2. segments
    flags = [
        "returning",
        "thin_history",
        "volatile",
        "usage_shift",
        "questionable_flag",
        "new_team",
        "top_teammate_out",
    ]
    segments = {}
    for flag in flags:
        inside = res[res[flag].astype(bool)]
        outside = res[~res[flag].astype(bool)]
        if len(inside) < 50:
            continue
        segments[flag] = {
            "games": int(len(inside)),
            "share_of_games": float(len(inside) / len(res)),
            "share_of_total_error": float(inside.abs_error.sum() / total),
            "mae_inside": float(inside.abs_error.mean()),
            "mae_outside": float(outside.abs_error.mean()),
            "excess_mae": float(inside.abs_error.mean() - outside.abs_error.mean()),
            # If this segment were merely as predictable as a normal game, how much overall MAE
            # would we save? This is the prize for getting the segment right.
            "overall_mae_saved_if_fixed": float(
                (inside.abs_error.mean() - outside.abs_error.mean()) * len(inside) / len(res)
            ),
        }

    any_flag = res[flags].astype(bool).any(axis=1)
    union = {
        "share_of_games": float(any_flag.mean()),
        "share_of_total_error": float(res[any_flag].abs_error.sum() / total),
        "mae_inside": float(res[any_flag].abs_error.mean()),
        "mae_outside": float(res[~any_flag].abs_error.mean()),
        "overall_mae_saved_if_fixed": float(
            (res[any_flag].abs_error.mean() - res[~any_flag].abs_error.mean()) * any_flag.mean()
        ),
    }

    # --- 3. how much of the error is simply irreducible noise?
    # Compare the model's error against the error of a perfect forecast of each player's own
    # long-run mean: the gap between them is what any model could in principle still win.
    res["player_mean"] = res.groupby("player_id").ppr.transform("mean")
    irreducible = float(np.abs(res.ppr - res.player_mean).mean())

    result = {
        "player_games": int(len(res)),
        "overall_mae": mae,
        "concentration": concentration,
        "segments": segments,
        "any_segment": union,
        "mae_if_we_knew_each_players_true_season_mean": irreducible,
        "headroom_vs_that_oracle": float(mae - irreducible),
    }
    save("h_error_anatomy", result)

    print(f"player-games {len(res)}, overall MAE {mae:.3f}\n")
    print("error concentration:")
    for k, v in concentration.items():
        print(
            f"  {k:24s} {v['share_of_total_error']:.1%} of all error (mean {v['mean_error_in_group']:.1f})"
        )
    print("\nsegments identifiable before kickoff:")
    print(
        f"  {'segment':20s} {'games':>7s} {'%games':>7s} {'%error':>7s} {'MAE in':>7s} {'MAE out':>8s} {'excess':>7s} {'prize':>7s}"
    )
    for k, v in sorted(segments.items(), key=lambda kv: -kv[1]["overall_mae_saved_if_fixed"]):
        print(
            f"  {k:20s} {v['games']:>7d} {v['share_of_games']:>6.1%} {v['share_of_total_error']:>6.1%} "
            f"{v['mae_inside']:>7.2f} {v['mae_outside']:>8.2f} {v['excess_mae']:>+7.2f} {v['overall_mae_saved_if_fixed']:>+7.3f}"
        )
    print(
        f"\n  {'ANY of the above':20s} {'':>7s} {union['share_of_games']:>6.1%} {union['share_of_total_error']:>6.1%} "
        f"{union['mae_inside']:>7.2f} {union['mae_outside']:>8.2f} {union['mae_inside'] - union['mae_outside']:>+7.2f} "
        f"{union['overall_mae_saved_if_fixed']:>+7.3f}"
    )
    print(f"\nMAE if we knew each player's true season mean in advance: {irreducible:.3f}")
    print(f"headroom between our model and that oracle: {mae - irreducible:+.3f}")


if __name__ == "__main__":
    main()
