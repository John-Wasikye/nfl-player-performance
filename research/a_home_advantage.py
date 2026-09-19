"""A. Home-field advantage: how big is it, does it hit players, and is the 'loud stadium' effect real?

Questions
  A1  How much better do home teams do (points, win rate, offensive EPA per play), by season?
  A2  How much better do individual players score at home than away (same player, paired)?
  A3  Do some stadiums hurt visiting offenses more than others (false starts, EPA), and is that
      effect repeatable from one period to the next, or just noise?
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from common import connect, pbp, save, schedule, se
from scipy import stats


def a1_team_level(games: pd.DataFrame, plays: pd.DataFrame) -> dict:
    g = games[games.location != "Neutral"].copy()
    g["margin"] = g.home_score - g.away_score
    g["home_win"] = np.where(g.margin > 0, 1.0, np.where(g.margin == 0, 0.5, 0.0))
    by_season = g.groupby("season").agg(
        games=("game_id", "count"),
        home_pts=("home_score", "mean"),
        away_pts=("away_score", "mean"),
        margin=("margin", "mean"),
        home_win=("home_win", "mean"),
    )
    overall = {
        "games": int(len(g)),
        "home_points_minus_away": float(g.margin.mean()),
        "home_points_minus_away_se": se(g.margin),
        "home_win_rate": float(g.home_win.mean()),
    }

    p = plays[plays.play_type.isin(["pass", "run"]) & plays.epa.notna()]
    non_neutral = set(g.game_id)
    p = p[p.game_id.isin(non_neutral)]
    team_game = p.groupby(["game_id", "season", "posteam_type"]).epa.mean().unstack()
    team_game["home_minus_away_epa"] = team_game["home"] - team_game["away"]
    epa = {
        "home_epa_per_play": float(team_game["home"].mean()),
        "away_epa_per_play": float(team_game["away"].mean()),
        "home_minus_away": float(team_game.home_minus_away_epa.mean()),
        "se": se(team_game.home_minus_away_epa),
    }
    epa_by_season = team_game.groupby("season").home_minus_away_epa.mean()
    return {
        "overall": overall,
        "by_season": by_season.round(3).reset_index().to_dict("records"),
        "epa_per_play": epa,
        "epa_home_minus_away_by_season": epa_by_season.round(4).to_dict(),
    }


def a2_players(con, games: pd.DataFrame) -> dict:
    df = con.sql(
        """
        select f.player_id, f.season, f.week, f.position_group, f.team, f.game_id,
               p.fantasy_points_scored as pts
        from fct_player_week f
        join int_weekly_fantasy_points p using (player_id, season, week)
        where f.season_type = 'REG' and f.season between 2021 and 2025
          and f.position_group in ('QB','RB','WR','TE','K')
        """
    ).df()
    home = games[["game_id", "home_team", "location"]]
    df = df.merge(home, on="game_id")
    df = df[df.location != "Neutral"]
    df["is_home"] = df.team == df.home_team

    rows = []
    for (player, season, pos), grp in df.groupby(["player_id", "season", "position_group"]):
        h, a = grp[grp.is_home].pts, grp[~grp.is_home].pts
        if len(h) >= 4 and len(a) >= 4 and grp.pts.mean() >= 5:
            rows.append((pos, player, season, h.mean() - a.mean(), grp.pts.mean(), len(grp)))
    paired = pd.DataFrame(rows, columns=["position", "player", "season", "diff", "avg", "games"])
    out = {}
    for pos, grp in paired.groupby("position"):
        out[pos] = {
            "player_seasons": int(len(grp)),
            "home_minus_away_points": float(grp["diff"].mean()),
            "se": se(grp["diff"]),
            "avg_points": float(grp.avg.mean()),
            "pct_of_average": float(grp["diff"].mean() / grp.avg.mean() * 100),
        }
    out["ALL"] = {
        "player_seasons": int(len(paired)),
        "home_minus_away_points": float(paired["diff"].mean()),
        "se": se(paired["diff"]),
        "pct_of_average": float(paired["diff"].mean() / paired.avg.mean() * 100),
    }
    return out


def a3_stadiums(games: pd.DataFrame, plays: pd.DataFrame) -> dict:
    g = games[(games.location != "Neutral")][
        ["game_id", "season", "stadium_id", "roof", "home_team"]
    ]
    p = plays.merge(g.drop(columns=["season"]), on="game_id")

    # Visiting offense only.
    v = p[p.posteam_type == "away"]
    snaps = v[v.play_type.isin(["pass", "run"])].groupby("game_id").size().rename("snaps")
    fs = (
        v[(v.penalty == 1) & (v.penalty_type == "False Start") & (v.penalty_team == v.posteam)]
        .groupby("game_id")
        .size()
        .rename("false_starts")
    )
    epa = (
        v[v.play_type.isin(["pass", "run"]) & v.epa.notna()]
        .groupby("game_id")
        .epa.mean()
        .rename("epa")
    )
    game_v = g.set_index("game_id").join([snaps, fs, epa]).fillna({"false_starts": 0})
    game_v["snaps"] = game_v.snaps + game_v.false_starts
    game_v["visitor"] = v.groupby("game_id").posteam.first()

    # team-season adjustment for EPA: how did this visitor do relative to its own season average
    all_off = p[p.play_type.isin(["pass", "run"]) & p.epa.notna()]
    team_season = all_off.groupby(["season", "posteam"]).epa.mean().rename("team_avg_epa")
    game_v = game_v.reset_index().merge(
        team_season, left_on=["season", "visitor"], right_index=True
    )
    game_v["epa_vs_own_avg"] = game_v.epa - game_v.team_avg_epa

    league_fs_rate = game_v.false_starts.sum() / game_v.snaps.sum() * 100
    by_stadium = game_v.groupby("stadium_id").agg(
        home_team=("home_team", "last"),
        visits=("game_id", "count"),
        false_starts=("false_starts", "sum"),
        snaps=("snaps", "sum"),
        epa_vs_own_avg=("epa_vs_own_avg", "mean"),
    )
    by_stadium["fs_per_100"] = by_stadium.false_starts / by_stadium.snaps * 100
    by_stadium = by_stadium[by_stadium.visits >= 15]

    # 1) Is there more variation between stadiums than chance alone would produce?
    expected = by_stadium.snaps * league_fs_rate / 100
    chi2 = float(((by_stadium.false_starts - expected) ** 2 / expected).sum())
    dof = len(by_stadium) - 1
    fs_test = {"chi2": chi2, "dof": dof, "p_value": float(1 - stats.chi2.cdf(chi2, dof))}
    groups = [
        grp.epa_vs_own_avg.dropna().values
        for _, grp in game_v.groupby("stadium_id")
        if len(grp) >= 15
    ]
    f_stat, f_p = stats.f_oneway(*groups)
    epa_test = {"F": float(f_stat), "p_value": float(f_p), "stadiums": len(groups)}

    # 2) Is the stadium effect repeatable? Compare 2021-2023 with 2024-2025.
    early = game_v[game_v.season <= 2023].groupby("stadium_id")
    late = game_v[game_v.season >= 2024].groupby("stadium_id")
    e = pd.DataFrame(
        {
            "fs_early": early.false_starts.sum() / early.snaps.sum() * 100,
            "fs_late": late.false_starts.sum() / late.snaps.sum() * 100,
            "epa_early": early.epa_vs_own_avg.mean(),
            "epa_late": late.epa_vs_own_avg.mean(),
            "n_early": early.size(),
            "n_late": late.size(),
        }
    ).dropna()
    e = e[(e.n_early >= 8) & (e.n_late >= 6)]
    fs_r = stats.pearsonr(e.fs_early, e.fs_late)
    epa_r = stats.pearsonr(e.epa_early, e.epa_late)
    repeat = {
        "stadiums": int(len(e)),
        "false_start_rate_correlation": float(fs_r.statistic),
        "false_start_rate_p": float(fs_r.pvalue),
        "epa_correlation": float(epa_r.statistic),
        "epa_p": float(epa_r.pvalue),
    }

    # 3) Domes versus open air.
    game_v["indoor"] = game_v.roof.isin(["dome", "closed"])
    roof = game_v.groupby("indoor").agg(
        games=("game_id", "count"),
        fs=("false_starts", "sum"),
        snaps=("snaps", "sum"),
        epa_vs_own_avg=("epa_vs_own_avg", "mean"),
    )
    roof["fs_per_100"] = roof.fs / roof.snaps * 100
    indoor_g = game_v[game_v.indoor].epa_vs_own_avg.dropna()
    outdoor_g = game_v[~game_v.indoor].epa_vs_own_avg.dropna()
    roof_t = stats.ttest_ind(indoor_g, outdoor_g, equal_var=False)

    ranked = by_stadium.sort_values("fs_per_100", ascending=False)
    ranked_epa = by_stadium.sort_values("epa_vs_own_avg")
    return {
        "league_visitor_false_starts_per_100_snaps": float(league_fs_rate),
        "false_start_heterogeneity_test": fs_test,
        "epa_heterogeneity_test": epa_test,
        "repeatability_2021_23_vs_2024_25": repeat,
        "indoor_vs_outdoor": {
            "table": roof.round(3).reset_index().to_dict("records"),
            "epa_difference": float(indoor_g.mean() - outdoor_g.mean()),
            "t_test_p": float(roof_t.pvalue),
        },
        "highest_false_start_stadiums": ranked.head(6)[
            ["home_team", "visits", "fs_per_100", "epa_vs_own_avg"]
        ]
        .round(3)
        .reset_index()
        .to_dict("records"),
        "worst_for_visiting_epa": ranked_epa.head(6)[
            ["home_team", "visits", "fs_per_100", "epa_vs_own_avg"]
        ]
        .round(3)
        .reset_index()
        .to_dict("records"),
    }


def main() -> None:
    con = connect()
    games = schedule(con)
    plays = pbp(con)
    result = {
        "a1_team_level": a1_team_level(games, plays),
        "a2_players_paired": a2_players(con, games),
        "a3_stadiums": a3_stadiums(games, plays),
    }
    save("a_home_advantage", result)
    import json

    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
