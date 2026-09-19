"""D. Which factors improve next-game fantasy point predictions? (feature ablation on held-out seasons)
E. Weather effects on passing and kicking.   F. Game script: spreads and pass rate.
G. What happens to teammates' targets when a team's top receiver is out?

D builds one row per player-game (QB/RB/WR/TE) using only information known before kickoff, trains
LightGBM on 2021-2023 and scores 2024-2025, adding factor groups one at a time. Every trailing feature
is shifted so a game never sees itself or later games.
"""

from __future__ import annotations

import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from common import connect, pbp, save, schedule, se
from scipy import stats

warnings.filterwarnings("ignore")
POS = ["QB", "RB", "WR", "TE"]


def build_dataset(con) -> pd.DataFrame:
    df = con.sql(
        """
        select f.player_id, f.season, f.week, f.position_group as pos, f.team, f.opponent_team as opp,
               f.game_id, f.attempts, f.carries, f.targets, coalesce(f.target_share, 0) as target_share,
               f.injury_status, p.fantasy_points_scored as ppr
        from fct_player_week f
        join int_weekly_fantasy_points p using (player_id, season, week)
        where f.season_type = 'REG' and f.season between 2021 and 2025
          and f.position_group in ('QB','RB','WR','TE')
        """
    ).df()
    df = df.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    g = df.groupby("player_id")
    df["prior_games"] = g.cumcount()
    df["ewm"] = g.ppr.transform(lambda s: s.shift(1).ewm(alpha=0.3, min_periods=2).mean())
    df["mean3"] = g.ppr.transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    df["mean5"] = g.ppr.transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    df["mean10"] = g.ppr.transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    df["season_avg"] = df.groupby(["player_id", "season"]).ppr.transform(
        lambda s: s.shift(1).expanding(min_periods=1).mean()
    )
    df["std8"] = g.ppr.transform(lambda s: s.shift(1).rolling(8, min_periods=3).std())
    for c in ["attempts", "carries", "targets", "target_share"]:
        df[f"t5_{c}"] = g[c].transform(lambda s: s.shift(1).rolling(5, min_periods=2).mean())
    df = df[df.prior_games >= 3].copy()
    df = df[(df.mean5 >= 4)]

    sched = schedule(con)
    s = sched.set_index("game_id")
    home = df.team.values == s.loc[df.game_id, "home_team"].values
    df["is_home"] = home.astype(int)
    total = s.loc[df.game_id, "total_line"].values
    spread = s.loc[df.game_id, "spread_line"].values
    df["team_spread"] = np.where(home, spread, -spread)  # positive: this team is favored
    df["total_line"] = total
    df["implied_total"] = total / 2 + df.team_spread / 2
    df["divisional"] = s.loc[df.game_id, "is_divisional"].astype(float).values
    df["rest"] = np.where(
        home, s.loc[df.game_id, "home_rest"].values, s.loc[df.game_id, "away_rest"].values
    )
    roof = s.loc[df.game_id, "roof"].values
    df["indoor"] = pd.Series(roof).isin(["dome", "closed"]).astype(int).values
    df["wind"] = np.where(df.indoor == 1, 0, s.loc[df.game_id, "wind"].values)
    df["temp"] = np.where(df.indoor == 1, 70, s.loc[df.game_id, "temp"].values)

    # Opponent strength: fantasy points a defense has allowed to this position over its last 8 games.
    allowed = (
        con.sql(
            """
            select f.season, f.week, f.opponent_team as defense, f.position_group as pos,
                   sum(p.fantasy_points_scored) as pts
            from fct_player_week f join int_weekly_fantasy_points p using (player_id, season, week)
            where f.season_type = 'REG' and f.position_group in ('QB','RB','WR','TE')
            group by all
            """
        )
        .df()
        .sort_values(["defense", "pos", "season", "week"])
    )
    allowed["def_allowed8"] = allowed.groupby(["defense", "pos"]).pts.transform(
        lambda s: s.shift(1).rolling(8, min_periods=3).mean()
    )
    df = df.merge(
        allowed[["season", "week", "defense", "pos", "def_allowed8"]],
        left_on=["season", "week", "opp", "pos"],
        right_on=["season", "week", "defense", "pos"],
        how="left",
    )
    df["questionable"] = (df.injury_status == "Questionable").astype(int)
    df["pos_code"] = df.pos.map({p: i for i, p in enumerate(POS)})
    return df


FEATURES = {
    "history": [
        "ewm",
        "mean3",
        "mean5",
        "mean10",
        "season_avg",
        "std8",
        "prior_games",
        "pos_code",
        "t5_attempts",
        "t5_carries",
        "t5_targets",
        "t5_target_share",
    ],
    "game_context": [
        "implied_total",
        "team_spread",
        "total_line",
        "is_home",
        "divisional",
        "rest",
        "week",
    ],
    "opponent": ["def_allowed8"],
    "weather": ["wind", "temp", "indoor"],
    "injury_status": ["questionable"],
}


def fit_eval(train, test, cols) -> tuple[np.ndarray, lgb.Booster]:
    params = dict(
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
    model = lgb.train(params, lgb.Dataset(train[cols], train.ppr), num_boost_round=400)
    return model.predict(test[cols]), model


def metrics(y, pred) -> dict:
    return {
        "mae": float(np.mean(np.abs(y - pred))),
        "rmse": float(np.sqrt(np.mean((y - pred) ** 2))),
        "spearman": float(stats.spearmanr(y, pred).statistic),
        "r2": float(1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)),
    }


def d_ablation(df: pd.DataFrame) -> dict:
    train, test = df[df.season <= 2023].copy(), df[df.season >= 2024].copy()
    out = {"train_rows": int(len(train)), "test_rows": int(len(test))}
    out["baselines"] = {
        name: metrics(test.ppr.values, test[name].fillna(test.mean10).values)
        for name in ["ewm", "mean5", "season_avg"]
    }
    steps, cols = {}, []
    for name, group in FEATURES.items():
        cols = cols + group
        pred, _ = fit_eval(train, test, cols)
        steps[f"+{name}"] = {
            "overall": metrics(test.ppr.values, pred),
            **{
                p: metrics(test.ppr[test.pos == p].values, pred[(test.pos == p).values])
                for p in POS
            },
        }
    out["cumulative"] = steps
    # Leave-one-group-out from the full model: what does each group add on top of everything else?
    full = [c for g in FEATURES.values() for c in g]
    full_pred, model = fit_eval(train, test, full)
    base = metrics(test.ppr.values, full_pred)
    drop = {}
    for name, group in FEATURES.items():
        cols_wo = [c for c in full if c not in group]
        pred, _ = fit_eval(train, test, cols_wo)
        m = metrics(test.ppr.values, pred)
        drop[name] = {
            "mae_without": m["mae"],
            "mae_full": base["mae"],
            "mae_increase_when_removed": m["mae"] - base["mae"],
        }
    out["drop_one_group"] = drop
    imp = pd.Series(model.feature_importance("gain"), index=full)
    out["top_features_by_gain"] = (
        (imp / imp.sum()).sort_values(ascending=False).head(10).round(3).to_dict()
    )

    # Home effect after accounting for everything else
    test2 = test.copy()
    test2["pred"] = full_pred
    test2["resid"] = test2.ppr - test2.pred
    out["residual_by_home"] = {
        str(h): float(test2[test2.is_home == h].resid.mean()) for h in (0, 1)
    }
    # Calibration of the point prediction by decile
    test2["decile"] = pd.qcut(test2.pred, 10, labels=False)
    out["calibration_by_decile"] = (
        test2.groupby("decile")
        .agg(pred=("pred", "mean"), actual=("ppr", "mean"))
        .round(2)
        .to_dict("list")
    )
    return out


def e_weather(con, plays: pd.DataFrame, sched: pd.DataFrame) -> dict:
    s = sched[sched.roof.isin(["outdoors", "open"]) & sched.wind.notna() & sched.temp.notna()][
        ["game_id", "wind", "temp"]
    ]
    p = plays.merge(s, on="game_id")
    db = p[(p.qb_dropback == 1) & p.epa.notna()]
    game = db.groupby("game_id").agg(
        epa_per_dropback=("epa", "mean"), wind=("wind", "first"), temp=("temp", "first")
    )
    game["wind_bin"] = pd.cut(game.wind, [-1, 9, 14, 100], labels=["0-9", "10-14", "15+"])
    game["temp_bin"] = pd.cut(game.temp, [-50, 39, 59, 200], labels=["<40", "40-59", "60+"])
    wind = (
        game.groupby("wind_bin", observed=True).epa_per_dropback.agg(["mean", "count", se]).round(4)
    )
    temp = (
        game.groupby("temp_bin", observed=True).epa_per_dropback.agg(["mean", "count", se]).round(4)
    )
    fg = p[p.field_goal_result.notna() & (p.kick_distance >= 30)].copy()
    fg["made"] = (fg.field_goal_result == "made").astype(int)
    fg["wind_bin"] = pd.cut(fg.wind, [-1, 9, 14, 100], labels=["0-9", "10-14", "15+"])
    fg["dist_bin"] = pd.cut(fg.kick_distance, [29, 39, 49, 80])
    fgt = (
        fg.groupby("wind_bin", observed=True)
        .agg(
            attempts=("made", "size"), pct=("made", "mean"), mean_distance=("kick_distance", "mean")
        )
        .round(3)
    )
    # distance-adjusted: residual vs league make rate for the same distance bin
    league = fg.groupby("dist_bin", observed=True).made.mean().rename("exp")
    fg = fg.join(league, on="dist_bin")
    fg["over_exp"] = fg.made - fg.exp
    adj = fg.groupby("wind_bin", observed=True).over_exp.agg(["mean", "count", se]).round(4)
    pts = sched[sched.roof.isin(["outdoors", "open"]) & sched.wind.notna()].copy()
    pts["total_pts"] = pts.home_score + pts.away_score
    pts["wind_bin"] = pd.cut(pts.wind, [-1, 9, 14, 100], labels=["0-9", "10-14", "15+"])
    tp = pts.groupby("wind_bin", observed=True).total_pts.agg(["mean", "count", se]).round(2)
    return {
        "epa_per_dropback_by_wind_mph": wind.reset_index().to_dict("records"),
        "epa_per_dropback_by_temp_f": temp.reset_index().to_dict("records"),
        "field_goals_30plus_by_wind": fgt.reset_index().to_dict("records"),
        "field_goal_make_rate_vs_distance_expected_by_wind": adj.reset_index().to_dict("records"),
        "game_total_points_by_wind": tp.reset_index().to_dict("records"),
    }


def f_game_script(plays: pd.DataFrame, sched: pd.DataFrame) -> dict:
    s = sched.set_index("game_id")
    p = plays[plays.play_type.isin(["pass", "run"]) & plays.posteam.notna()]
    tg = (
        p.groupby(["game_id", "posteam", "posteam_type"])
        .agg(plays=("play_type", "size"), passes=("play_type", lambda x: (x == "pass").sum()))
        .reset_index()
    )
    tg["pass_rate"] = tg.passes / tg.plays
    sp = s.loc[tg.game_id, "spread_line"].values
    tg["team_spread"] = np.where(tg.posteam_type == "home", sp, -sp)
    total = s.loc[tg.game_id, "total_line"].values
    tg["implied"] = total / 2 + tg.team_spread / 2
    pts = np.where(
        tg.posteam_type == "home",
        s.loc[tg.game_id, "home_score"].values,
        s.loc[tg.game_id, "away_score"].values,
    )
    tg["points"] = pts
    tg["spread_bin"] = pd.cut(
        tg.team_spread,
        [-30, -7.01, -3.01, 3, 7, 30],
        labels=["underdog 7+", "underdog 3-7", "pick'em (+/-3)", "favorite 3-7", "favorite 7+"],
    )
    by = (
        tg.groupby("spread_bin", observed=True)
        .agg(
            games=("pass_rate", "size"),
            pass_rate=("pass_rate", "mean"),
            plays=("plays", "mean"),
            points=("points", "mean"),
        )
        .round(3)
    )
    r = stats.pearsonr(tg.implied, tg.points)
    slope = np.polyfit(tg.implied, tg.points, 1)
    return {
        "by_spread": by.reset_index().to_dict("records"),
        "implied_total_vs_actual_points": {
            "r": float(r.statistic),
            "slope": float(slope[0]),
            "intercept": float(slope[1]),
            "games": int(len(tg)),
        },
    }


def g_teammates(con, sched: pd.DataFrame) -> dict:
    df = (
        con.sql(
            """
        select f.player_id, f.season, f.week, f.team, f.position_group as pos, f.targets, f.game_id
        from fct_player_week f
        where f.season_type='REG' and f.season between 2021 and 2025 and f.position_group in ('WR','TE','RB')
        """
        )
        .df()
        .sort_values(["player_id", "season", "week"])
    )
    df["t5"] = df.groupby("player_id").targets.transform(
        lambda s: s.shift(1).rolling(5, min_periods=3).mean()
    )
    inj = con.sql(
        "select player_id, season, week, report_status from stg_injuries where report_status in ('Out','Doubtful')"
    ).df()
    key = df.groupby(["team", "season", "week"])
    rows = []
    for (team, season, week), grp in key:
        prev = df[(df.team == team) & (df.season == season) & (df.week < week)]
        if prev.empty:
            continue
        cand = prev[prev.pos == "WR"].sort_values(["season", "week"]).groupby("player_id").tail(1)
        cand = cand.dropna(subset=["t5"])
        if len(cand) < 2:
            continue
        wr1 = cand.sort_values("t5", ascending=False).iloc[0]
        if wr1.t5 < 5:
            continue
        present = (grp.player_id == wr1.player_id).any()
        out_flag = (
            (inj.player_id == wr1.player_id) & (inj.season == season) & (inj.week == week)
        ).any()
        others = (
            grp[(grp.player_id != wr1.player_id) & grp.t5.notna()]
            .sort_values("t5", ascending=False)
            .head(3)
        )
        if len(others) < 2:
            continue
        rows.append(
            {
                "wr1_out": (not present) and out_flag,
                "wr1_present": present,
                "delta_top3_others": (others.targets - others.t5).mean(),
                "delta_team_targets": (grp.targets.sum() - grp.t5.fillna(0).sum()),
            }
        )
    r = pd.DataFrame(rows)
    out_g, ctl = r[r.wr1_out], r[r.wr1_present]
    return {
        "team_games_wr1_out": int(len(out_g)),
        "team_games_wr1_present": int(len(ctl)),
        "extra_targets_for_next_three_options_out": {
            "mean": float(out_g.delta_top3_others.mean()),
            "se": se(out_g.delta_top3_others),
        },
        "extra_targets_for_next_three_options_present": {
            "mean": float(ctl.delta_top3_others.mean()),
            "se": se(ctl.delta_top3_others),
        },
    }


def main() -> None:
    con = connect()
    sched = schedule(con)
    plays = pbp(con)
    df = build_dataset(con)
    result = {
        "d_ablation": d_ablation(df),
        "e_weather": e_weather(con, plays, sched),
        "f_game_script": f_game_script(plays, sched),
        "g_teammates": g_teammates(con, sched),
    }
    save("d_context_ablation", result)
    import json

    print(json.dumps(result, indent=1, default=float))


if __name__ == "__main__":
    main()
