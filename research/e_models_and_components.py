"""E2. Model family comparison and how predictable each stat is (yards, touchdowns, volume).

  1  Same features, different models on next-game fantasy points: naive average, ridge, LightGBM,
     and an ensemble. Also checks whether quantile models give honest prediction intervals.
  2  Each stat component predicted separately (targets, receptions, yards, touchdowns...) to see
     which parts of a fantasy score are predictable and which are mostly luck.
Train 2021-2023, test 2024-2025.
"""

from __future__ import annotations

import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from common import connect, save, schedule
from scipy import stats
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

COMPONENTS = {
    "QB": [
        "attempts",
        "passing_yards",
        "passing_tds",
        "passing_interceptions",
        "rushing_yards",
        "rushing_tds",
        "ppr",
    ],
    "RB": [
        "carries",
        "rushing_yards",
        "rushing_tds",
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "ppr",
    ],
    "WR": ["targets", "receptions", "receiving_yards", "receiving_tds", "ppr"],
    "TE": ["targets", "receptions", "receiving_yards", "receiving_tds", "ppr"],
}


def load(con) -> pd.DataFrame:
    df = con.sql(
        """
        select f.player_id, f.season, f.week, f.position_group as pos, f.team, f.game_id,
               f.attempts, f.passing_yards, f.passing_tds, f.passing_interceptions,
               f.carries, f.rushing_yards, f.rushing_tds, f.targets, f.receptions,
               f.receiving_yards, f.receiving_tds, p.fantasy_points_scored as ppr
        from fct_player_week f join int_weekly_fantasy_points p using (player_id, season, week)
        where f.season_type = 'REG' and f.season between 2021 and 2025 and f.position_group in ('QB','RB','WR','TE')
        """
    ).df()
    df = df.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    g = df.groupby("player_id")
    df["prior_games"] = g.cumcount()
    s = schedule(con).set_index("game_id")
    home = df.team.values == s.loc[df.game_id, "home_team"].values
    df["is_home"] = home.astype(int)
    sp = s.loc[df.game_id, "spread_line"].values
    tot = s.loc[df.game_id, "total_line"].values
    df["team_spread"] = np.where(home, sp, -sp)
    df["implied_total"] = tot / 2 + df.team_spread / 2
    df["total_line"] = tot
    return df


def add_trailing(df: pd.DataFrame, col: str) -> None:
    g = df.groupby("player_id")[col]
    df[f"{col}_m10"] = g.transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    df[f"{col}_m5"] = g.transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    df[f"{col}_ewm"] = g.transform(lambda s: s.shift(1).ewm(alpha=0.3, min_periods=2).mean())


def r2(y, p) -> float:
    return float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))


def part1_models(df: pd.DataFrame) -> dict:
    add_trailing(df, "ppr")
    for c in ["attempts", "carries", "targets"]:
        add_trailing(df, c)
    df["season_avg"] = df.groupby(["player_id", "season"]).ppr.transform(
        lambda s: s.shift(1).expanding().mean()
    )
    d = df[(df.prior_games >= 3) & (df.ppr_m5 >= 4)].copy()
    d["pos_code"] = d.pos.map({"QB": 0, "RB": 1, "WR": 2, "TE": 3})
    cols = [
        "ppr_m10",
        "ppr_m5",
        "ppr_ewm",
        "season_avg",
        "prior_games",
        "pos_code",
        "attempts_m5",
        "carries_m5",
        "targets_m5",
        "implied_total",
        "team_spread",
        "total_line",
        "is_home",
    ]
    train, test = d[d.season <= 2023], d[d.season >= 2024]
    y = test.ppr.values
    out = {"test_rows": int(len(test))}

    naive = test.ppr_ewm.fillna(test.ppr_m10).values
    out["naive_ewm"] = {"mae": float(np.mean(np.abs(y - naive))), "r2": r2(y, naive)}

    Xtr = train[cols].fillna(train[cols].median())
    Xte = test[cols].fillna(train[cols].median())
    ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))).fit(
        Xtr, train.ppr
    )
    pr = ridge.predict(Xte)
    out["ridge"] = {"mae": float(np.mean(np.abs(y - pr))), "r2": r2(y, pr)}

    params = dict(
        objective="regression",
        learning_rate=0.03,
        num_leaves=8,
        min_data_in_leaf=100,
        feature_fraction=0.8,
        bagging_fraction=0.8,
        bagging_freq=1,
        lambda_l2=10.0,
        verbose=-1,
        seed=3,
    )
    gbm = lgb.train(params, lgb.Dataset(train[cols], train.ppr), num_boost_round=350)
    pg = gbm.predict(test[cols])
    out["lightgbm"] = {"mae": float(np.mean(np.abs(y - pg))), "r2": r2(y, pg)}
    ens = 0.5 * pr + 0.5 * pg
    out["ensemble_ridge_lightgbm"] = {
        "mae": float(np.mean(np.abs(y - ens))),
        "r2": r2(y, ens),
        "spearman": float(stats.spearmanr(y, ens).statistic),
    }
    ens3 = (pr + pg + naive) / 3
    out["ensemble_ridge_lightgbm_naive"] = {
        "mae": float(np.mean(np.abs(y - ens3))),
        "r2": r2(y, ens3),
    }
    coef = dict(zip(cols, ridge[-1].coef_.round(3), strict=True))
    out["ridge_standardized_coefficients"] = coef

    # Quantile models for honest ranges: do the 10%-90% intervals contain 80% of outcomes?
    q = {}
    for alpha in (0.1, 0.5, 0.9):
        m = lgb.train(
            {**params, "objective": "quantile", "alpha": alpha},
            lgb.Dataset(train[cols], train.ppr),
            num_boost_round=350,
        )
        q[alpha] = m.predict(test[cols])
    lo, hi = np.minimum(q[0.1], q[0.9]), np.maximum(q[0.1], q[0.9])
    out["quantile_interval_10_90"] = {
        "coverage": float(np.mean((y >= lo) & (y <= hi))),
        "mean_width": float(np.mean(hi - lo)),
        "below_p10": float(np.mean(y < q[0.1])),
        "above_p90": float(np.mean(y > q[0.9])),
    }
    # split-conformal correction using the last training season as calibration
    tr2, cal = d[d.season <= 2022], d[d.season == 2023]
    mlo = lgb.train(
        {**params, "objective": "quantile", "alpha": 0.1},
        lgb.Dataset(tr2[cols], tr2.ppr),
        num_boost_round=350,
    )
    mhi = lgb.train(
        {**params, "objective": "quantile", "alpha": 0.9},
        lgb.Dataset(tr2[cols], tr2.ppr),
        num_boost_round=350,
    )
    scores = np.maximum(
        mlo.predict(cal[cols]) - cal.ppr.values, cal.ppr.values - mhi.predict(cal[cols])
    )
    qhat = np.quantile(scores, 0.8 * (1 + 1 / len(scores)))
    lo2, hi2 = mlo.predict(test[cols]) - qhat, mhi.predict(test[cols]) + qhat
    out["conformalized_interval_80"] = {
        "coverage": float(np.mean((y >= lo2) & (y <= hi2))),
        "mean_width": float(np.mean(hi2 - lo2)),
        "qhat": float(qhat),
    }
    return out


def part2_components(df: pd.DataFrame) -> dict:
    out = {}
    for pos, comps in COMPONENTS.items():
        d0 = df[df.pos == pos].copy()
        for c in comps:
            add_trailing(d0, c)
        d0["season_avg"] = d0.groupby(["player_id", "season"]).ppr.transform(
            lambda s: s.shift(1).expanding().mean()
        )
        d0 = d0[(d0.prior_games >= 3) & (d0.ppr_m5 >= 4)]
        train, test = d0[d0.season <= 2023], d0[d0.season >= 2024]
        res = {}
        for c in comps:
            cols = [
                f"{c}_m10",
                f"{c}_m5",
                f"{c}_ewm",
                "prior_games",
                "implied_total",
                "team_spread",
                "total_line",
                "is_home",
            ]
            params = dict(
                objective="regression",
                learning_rate=0.03,
                num_leaves=8,
                min_data_in_leaf=60,
                feature_fraction=0.8,
                bagging_fraction=0.8,
                bagging_freq=1,
                lambda_l2=10.0,
                verbose=-1,
                seed=3,
            )
            m = lgb.train(params, lgb.Dataset(train[cols], train[c]), num_boost_round=300)
            p = m.predict(test[cols])
            y = test[c].values
            naive = test[f"{c}_ewm"].fillna(test[f"{c}_m10"]).values
            res[c] = {
                "r2_model": round(r2(y, p), 3),
                "r2_naive_trailing_average": round(r2(y, naive), 3),
                "spearman_model": round(float(stats.spearmanr(y, p).statistic), 3),
                "mean_actual": round(float(y.mean()), 2),
                "share_of_games_zero": round(float((y == 0).mean()), 3),
            }
        out[pos] = {"test_rows": int(len(test)), "components": res}
    return out


def main() -> None:
    con = connect()
    df = load(con)
    result = {"models": part1_models(df.copy()), "components": part2_components(df.copy())}
    save("e_models_and_components", result)
    import json

    print(json.dumps(result, indent=1, default=float))


if __name__ == "__main__":
    main()
