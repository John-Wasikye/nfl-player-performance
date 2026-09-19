"""A4. Do some teams have a bigger home-field edge than others, and does it last?

For each team: (average point margin at home) minus (average point margin on the road). If crowd
noise or stadium quirks were a stable team trait, this gap would correlate between two separate
periods. Compares 2021-2023 with 2024-2025, and odd with even seasons.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from common import connect, save, schedule
from scipy import stats


def team_edges(g: pd.DataFrame) -> pd.Series:
    home = g.assign(team=g.home_team, margin=g.home_score - g.away_score, home=1)
    away = g.assign(team=g.away_team, margin=g.away_score - g.home_score, home=0)
    t = pd.concat([home, away])
    by = t.groupby(["team", "home"]).margin.mean().unstack()
    return by[1] - by[0]


def main() -> None:
    g = schedule(connect())
    g = g[g.location != "Neutral"]
    early, late = g[g.season <= 2023], g[g.season >= 2024]
    odd, even = g[g.season % 2 == 1], g[g.season % 2 == 0]
    out = {}
    for name, (a, b) in {
        "2021-23_vs_2024-25": (early, late),
        "odd_vs_even_seasons": (odd, even),
    }.items():
        ea, eb = team_edges(a), team_edges(b)
        j = pd.concat([ea, eb], axis=1, keys=["a", "b"]).dropna()
        r = stats.pearsonr(j.a, j.b)
        out[name] = {"teams": int(len(j)), "r": float(r.statistic), "p": float(r.pvalue)}
    all_edges = team_edges(g)
    out["spread_of_team_edges_points"] = {
        "mean": float(all_edges.mean()),
        "sd_across_teams": float(all_edges.std()),
        "expected_sd_from_luck_alone": float(
            np.sqrt(2) * g.assign(m=g.home_score - g.away_score).m.std() / np.sqrt(len(g) / 32)
        ),
    }
    top = all_edges.sort_values(ascending=False)
    out["largest_home_edges"] = top.head(5).round(2).to_dict()
    out["smallest_home_edges"] = top.tail(5).round(2).to_dict()
    save("a4_team_home_edge", out)
    import json

    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
