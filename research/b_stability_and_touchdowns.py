"""B. Which player statistics are skill (repeatable) and which are luck?  C. Can touchdowns be predicted?

B  Year-to-year and within-season (odd vs even weeks) correlations of usage and efficiency stats.
   Stats that correlate strongly across seasons are safe to project from history; weak ones must be
   shrunk hard toward the position average.
C  Touchdowns: are they over-dispersed relative to a Poisson count, does an 'expected touchdowns'
   model built from where each touch happened beat a player's own recent touchdown total, and how
   much of next game's touchdowns is predictable at all?
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from common import connect, pbp, save

MIN_VOLUME = {
    "WR": ("targets", 40),
    "TE": ("targets", 40),
    "RB": ("carries", 80),
    "QB": ("attempts", 150),
}


def player_weeks(con) -> pd.DataFrame:
    return con.sql(
        """
        select f.player_id, f.season, f.week, f.position_group as pos, f.team,
               f.attempts, f.completions, f.passing_yards, f.passing_tds, f.passing_interceptions,
               f.carries, f.rushing_yards, f.rushing_tds, f.targets, f.receptions, f.receiving_yards,
               f.receiving_tds, coalesce(f.target_share, 0) as target_share,
               f.fg_att, f.fg_made, p.fantasy_points_scored as ppr
        from fct_player_week f
        join int_weekly_fantasy_points p using (player_id, season, week)
        where f.season_type = 'REG' and f.season between 2021 and 2025
          and f.position_group in ('QB','RB','WR','TE','K')
        """
    ).df()


def metric_table(df: pd.DataFrame, pos: str) -> pd.DataFrame:
    """Per-player metrics computed from a set of games (already filtered to that position)."""
    g = df.groupby("player_id")
    t = g.agg(
        games=("week", "count"),
        attempts=("attempts", "sum"),
        completions=("completions", "sum"),
        pass_yds=("passing_yards", "sum"),
        pass_td=("passing_tds", "sum"),
        ints=("passing_interceptions", "sum"),
        carries=("carries", "sum"),
        rush_yds=("rushing_yards", "sum"),
        rush_td=("rushing_tds", "sum"),
        targets=("targets", "sum"),
        rec=("receptions", "sum"),
        rec_yds=("receiving_yards", "sum"),
        rec_td=("receiving_tds", "sum"),
        target_share=("target_share", "mean"),
        ppr=("ppr", "mean"),
        fg_att=("fg_att", "sum"),
        fg_made=("fg_made", "sum"),
    )
    m = pd.DataFrame(index=t.index)
    if pos in ("WR", "TE"):
        m["targets_per_game"] = t.targets / t.games
        m["target_share"] = t.target_share
        m["yards_per_target"] = t.rec_yds / t.targets
        m["catch_rate"] = t.rec / t.targets
        m["td_per_target"] = t.rec_td / t.targets
        m["ppr_per_game"] = t.ppr
    elif pos == "RB":
        m["carries_per_game"] = t.carries / t.games
        m["targets_per_game"] = t.targets / t.games
        m["yards_per_carry"] = t.rush_yds / t.carries
        m["td_per_carry"] = t.rush_td / t.carries
        m["ppr_per_game"] = t.ppr
    elif pos == "QB":
        m["attempts_per_game"] = t.attempts / t.games
        m["yards_per_attempt"] = t.pass_yds / t.attempts
        m["td_rate"] = t.pass_td / t.attempts
        m["int_rate"] = t.ints / t.attempts
        m["completion_pct"] = t.completions / t.attempts
        m["rush_yards_per_game"] = t.rush_yds / t.games
        m["ppr_per_game"] = t.ppr
    m["volume"] = t[MIN_VOLUME[pos][0]]
    return m


def b_stability(weeks: pd.DataFrame) -> dict:
    out: dict = {}
    for pos in ("QB", "RB", "WR", "TE"):
        col, minimum = MIN_VOLUME[pos]
        d = weeks[weeks.pos == pos]
        # --- year to year
        pairs = []
        for season in range(2021, 2025):
            a = metric_table(d[d.season == season], pos)
            b = metric_table(d[d.season == season + 1], pos)
            j = a.join(b, lsuffix="_a", rsuffix="_b", how="inner")
            j = j[(j.volume_a >= minimum) & (j.volume_b >= minimum)]
            pairs.append(j)
        yy = pd.concat(pairs)
        metrics = [c for c in metric_table(d, pos).columns if c != "volume"]
        y2y = {m: float(np.corrcoef(yy[f"{m}_a"], yy[f"{m}_b"])[0, 1]) for m in metrics}
        # --- odd/even weeks split half within a season (Spearman-Brown corrected)
        halves = []
        for season in range(2021, 2026):
            ds = d[d.season == season]
            odd = metric_table(ds[ds.week % 2 == 1], pos)
            even = metric_table(ds[ds.week % 2 == 0], pos)
            j = odd.join(even, lsuffix="_o", rsuffix="_e", how="inner")
            j = j[(j.volume_o >= minimum / 2.2) & (j.volume_e >= minimum / 2.2)]
            halves.append(j)
        sh = pd.concat(halves)
        rel = {}
        for m in metrics:
            r = float(np.corrcoef(sh[f"{m}_o"], sh[f"{m}_e"])[0, 1])
            rel[m] = 2 * r / (1 + r)
        out[pos] = {
            "player_season_pairs": int(len(yy)),
            "year_to_year_r": {k: round(v, 3) for k, v in y2y.items()},
            "split_half_reliability_full_season": {k: round(v, 3) for k, v in rel.items()},
        }
    return out


# ---------------------------------------------------------------- touchdowns


BUCKETS = [0, 1, 2, 3, 5, 10, 20, 40, 100]
LABELS = ["1", "2", "3", "4-5", "6-10", "11-20", "21-40", "41+"]


def bucket(yardline: pd.Series) -> pd.Series:
    return pd.cut(yardline, bins=BUCKETS, labels=LABELS, right=True)


def touches(plays: pd.DataFrame) -> pd.DataFrame:
    """One row per rush attempt or target, with the player, field position and whether it scored."""
    rush = plays[
        (plays.rush_attempt == 1) & plays.rusher_player_id.notna() & plays.yardline_100.notna()
    ]
    rush = pd.DataFrame(
        {
            "game_id": rush.game_id,
            "season": rush.season,
            "week": rush.week,
            "player_id": rush.rusher_player_id,
            "kind": "rush",
            "yardline": rush.yardline_100,
            "td": (rush.rush_touchdown == 1).astype(int),
        }
    )
    tgt = plays[
        (plays.pass_attempt == 1) & plays.receiver_player_id.notna() & plays.yardline_100.notna()
    ]
    tgt = pd.DataFrame(
        {
            "game_id": tgt.game_id,
            "season": tgt.season,
            "week": tgt.week,
            "player_id": tgt.receiver_player_id,
            "kind": "target",
            "yardline": tgt.yardline_100,
            "td": ((tgt.pass_touchdown == 1) & (tgt.td_player_id == tgt.receiver_player_id)).astype(
                int
            ),
        }
    )
    t = pd.concat([rush, tgt], ignore_index=True)
    t["bucket"] = bucket(t.yardline)
    return t


def c_touchdowns(con, plays: pd.DataFrame, weeks: pd.DataFrame) -> dict:
    t = touches(plays)
    train = t[t.season <= 2023]
    rates = train.groupby(["kind", "bucket"], observed=True).td.mean().rename("p_td")
    t = t.join(rates, on=["kind", "bucket"])
    rate_table = {f"{k}|{b}": round(float(v), 4) for (k, b), v in rates.items()}

    pg = t.groupby(["player_id", "season", "week"]).agg(
        xtd=("p_td", "sum"), td=("td", "sum"), touches=("td", "size")
    )
    pg = pg.reset_index()
    info = weeks[weeks.pos.isin(["RB", "WR", "TE"])][["player_id", "season", "week", "pos"]]
    pg = pg.merge(info, on=["player_id", "season", "week"])

    held = pg[pg.season >= 2024]
    calib = {}
    for pos, grp in held.groupby("pos"):
        mu = grp.xtd.clip(lower=1e-6)
        calib[pos] = {
            "player_games": int(len(grp)),
            "actual_tds": int(grp.td.sum()),
            "expected_tds": float(grp.xtd.sum()),
            "variance_to_mean_of_tds": float(grp.td.var() / grp.td.mean()),
            "pearson_dispersion_vs_poisson": float((((grp.td - mu) ** 2) / mu).mean()),
        }

    # Predicting the NEXT game's touchdowns from trailing windows.
    pg = pg.sort_values(["player_id", "season", "week"]).reset_index(drop=True)
    grp = pg.groupby("player_id")
    win = 6
    pg["trail_td"] = grp.td.transform(lambda s: s.shift(1).rolling(win, min_periods=4).mean())
    pg["trail_xtd"] = grp.xtd.transform(lambda s: s.shift(1).rolling(win, min_periods=4).mean())
    pg["trail_touches"] = grp.touches.transform(
        lambda s: s.shift(1).rolling(win, min_periods=4).mean()
    )
    test = pg[(pg.season >= 2024) & pg.trail_td.notna() & (pg.trail_touches >= 6)]
    pred = {}
    for pos, d in test.groupby("pos"):
        pred[pos] = {
            "player_games": int(len(d)),
            "r_next_td_vs_trailing_actual_tds": float(np.corrcoef(d.td, d.trail_td)[0, 1]),
            "r_next_td_vs_trailing_expected_tds": float(np.corrcoef(d.td, d.trail_xtd)[0, 1]),
            "r_next_td_vs_trailing_touches": float(np.corrcoef(d.td, d.trail_touches)[0, 1]),
        }
    allr = {
        "r_actual": float(np.corrcoef(test.td, test.trail_td)[0, 1]),
        "r_expected": float(np.corrcoef(test.td, test.trail_xtd)[0, 1]),
        "r_touches": float(np.corrcoef(test.td, test.trail_touches)[0, 1]),
        "share_of_games_with_a_td": float((test.td > 0).mean()),
        "mean_tds_per_game": float(test.td.mean()),
    }
    # How much variance in next game's TD count could ANY model explain? (R^2 of the expected count)
    r2 = float(np.corrcoef(test.td, test.trail_xtd)[0, 1] ** 2)
    return {
        "xtd_rate_by_field_position": rate_table,
        "calibration_2024_25": calib,
        "next_game_prediction": pred,
        "next_game_prediction_all": allr,
        "r_squared_of_trailing_xtd": r2,
    }


def main() -> None:
    con = connect()
    weeks = player_weeks(con)
    result = {
        "b_stability": b_stability(weeks),
        "c_touchdowns": c_touchdowns(con, pbp(con), weeks),
    }
    save("b_stability_and_touchdowns", result)
    import json

    print(json.dumps(result, indent=2, default=float))


if __name__ == "__main__":
    main()
