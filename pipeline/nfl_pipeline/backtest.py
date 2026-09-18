"""Backtest: does a player's rank at week N predict their fantasy points in week N+1?

For every season, week, and position the rankings are built "as of" that week using only games
through it (there is a test for that), so each ranking can be scored against what happened next.

For each position and week we measure, over players who were ranked at week N and played in week
N+1 (players who did not play are excluded, as the plan says):

  * Spearman rank correlation between the ranking score and the next-week outcome, and
  * lift: how much more the top-ranked players produced than the average ranked player (the top 12
    QB/TE/K, top 24 RB/WR).

Two outcomes are scored: next-week fantasy points (the headline) and next-week total EPA (not
available for kickers).

The composite score is 'w * efficiency + (1 - w) * production' for a grid of efficiency weights w,
compared with two simple baselines: season-to-date fantasy points, and fantasy points per game.
The weight is chosen on the earlier seasons only and then confirmed on held-out later seasons, so
the reported result is not overfit. Nothing here changes the live ranking settings: it reports, and
a person decides.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb

POSITIONS = ("QB", "RB", "WR", "TE", "K")
TOP_K = {"QB": 12, "RB": 24, "WR": 24, "TE": 12, "K": 12}
EFFICIENCY_WEIGHTS = (0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0)
BASELINES = ("ppr_total", "ppr_per_game")
MIN_POOL = 8  # groups with fewer ranked players than this are too small to score meaningfully
CURRENT_WEIGHT = 0.7  # the setting in ranking_config today
OUTCOMES = {"points": "next_points", "epa": "next_epa"}
# Tuning weights within this much of the best average Spearman are treated as tied, and the tie is
# resolved toward the higher efficiency weight (the project's stated preference for efficiency).
TIE_TOLERANCE = 0.005
WEEK_BUCKETS = {"weeks 1-5": (1, 5), "weeks 6-11": (6, 11), "weeks 12+": (12, 99)}


def method_name(weight: float) -> str:
    return f"composite_{round(weight * 100):03d}"


def average_ranks(values: Sequence[float]) -> list[float]:
    """Ranks starting at 1, with tied values sharing the average of the ranks they span."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mean_x, mean_y = sum(x) / n, sum(y) / n
    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True))
    variance_x = sum((a - mean_x) ** 2 for a in x)
    variance_y = sum((b - mean_y) ** 2 for b in y)
    if variance_x == 0 or variance_y == 0:
        return None
    return covariance / math.sqrt(variance_x * variance_y)


def spearman(scores: Sequence[float], outcomes: Sequence[float]) -> float | None:
    """Rank correlation between a score and an outcome (None if it is undefined)."""
    return pearson(average_ranks(scores), average_ranks(outcomes))


def top_k_lift(
    scores: Sequence[float], outcomes: Sequence[float], ids: Sequence[str], k: int
) -> float | None:
    """Mean outcome of the k highest-scored players minus the mean outcome of everyone."""
    if len(scores) <= k:
        return None
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], ids[i]))
    top = [outcomes[i] for i in order[:k]]
    return sum(top) / k - sum(outcomes) / len(outcomes)


def mean_and_se(values: Sequence[float]) -> tuple[float | None, float | None]:
    """Mean and standard error of the mean (None when there are too few values)."""
    n = len(values)
    if n == 0:
        return None, None
    mean = sum(values) / n
    if n < 2:
        return mean, None
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(variance / n)


@dataclass(frozen=True)
class GroupResult:
    """One (season, week, position): each method's correlation and lift with next-week points."""

    season: int
    week: int
    position: str
    spearman: dict[str, float]
    lift: dict[str, float]


def load_pairs(connection: duckdb.DuckDBPyConnection) -> list[dict]:
    """Every ranked player-week paired with what that player scored the following week."""
    cursor = connection.execute(
        """
        select
            r.season, r.week, r.position_group as position, r.player_id,
            r.efficiency_score, r.production_score,
            r.ppr_points, r.ppr_per_game,
            nxt.fantasy_points_scored as next_points,
            -- total EPA created next week (not defined for kickers)
            case when r.position_group = 'K' then null else
                coalesce(nxt_stats.passing_epa, 0) + coalesce(nxt_stats.rushing_epa, 0)
                + coalesce(nxt_stats.receiving_epa, 0)
            end as next_epa
        from mart_rankings as r
        inner join int_weekly_fantasy_points as nxt
            on nxt.player_id = r.player_id
            and nxt.season = r.season
            and nxt.week = r.week + 1
            and nxt.season_type = 'REG'
        inner join fct_player_week as nxt_stats
            on nxt_stats.player_id = nxt.player_id
            and nxt_stats.season = nxt.season
            and nxt_stats.week = nxt.week
        where r.is_qualified
        order by r.season, r.week, r.position_group, r.player_id
        """
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def composite(row: dict, weight: float) -> float | None:
    efficiency, production = row["efficiency_score"], row["production_score"]
    if efficiency is None and production is None:
        return None
    if efficiency is None:
        return production
    if production is None:
        return efficiency
    return weight * efficiency + (1 - weight) * production


def score_groups(
    pairs: list[dict],
    weights: Sequence[float] = EFFICIENCY_WEIGHTS,
    outcome: str = "next_points",
) -> list[GroupResult]:
    groups: dict[tuple[int, int, str], list[dict]] = defaultdict(list)
    for row in pairs:
        if row[outcome] is not None:
            groups[(row["season"], row["week"], row["position"])].append(row)

    results = []
    for (season, week, position), rows in sorted(groups.items()):
        if len(rows) < MIN_POOL:
            continue
        outcomes = [r[outcome] for r in rows]
        ids = [r["player_id"] for r in rows]
        methods: dict[str, list[float]] = {
            "ppr_total": [r["ppr_points"] for r in rows],
            "ppr_per_game": [r["ppr_per_game"] for r in rows],
        }
        for weight in weights:
            methods[method_name(weight)] = [composite(r, weight) for r in rows]
        correlations: dict[str, float] = {}
        lifts: dict[str, float] = {}
        for name, scores in methods.items():
            if any(s is None for s in scores):
                continue
            rho = spearman(scores, outcomes)
            lift = top_k_lift(scores, outcomes, ids, TOP_K[position])
            if rho is not None:
                correlations[name] = rho
            if lift is not None:
                lifts[name] = lift
        results.append(GroupResult(season, week, position, correlations, lifts))
    return results


def _summarize(groups: list[GroupResult], method: str, position: str | None = None) -> dict:
    selected = [g for g in groups if position is None or g.position == position]
    rhos = [g.spearman[method] for g in selected if method in g.spearman]
    lifts = [g.lift[method] for g in selected if method in g.lift]
    rho, rho_se = mean_and_se(rhos)
    lift, lift_se = mean_and_se(lifts)
    return {
        "weeks": len(rhos),
        "spearman": _round(rho),
        "spearman_se": _round(rho_se),
        "lift": _round(lift),
        "lift_se": _round(lift_se),
    }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _average_across_positions(per_position: dict[str, dict], key: str) -> float | None:
    values = [p[key] for p in per_position.values() if p[key] is not None]
    return _round(sum(values) / len(values)) if values else None


def _paired_difference(
    groups: list[GroupResult], method: str, baseline: str, position: str
) -> dict:
    differences = [
        g.spearman[method] - g.spearman[baseline]
        for g in groups
        if g.position == position and method in g.spearman and baseline in g.spearman
    ]
    mean, se = mean_and_se(differences)
    return {"weeks": len(differences), "mean_difference": _round(mean), "se": _round(se)}


def choose_weight(average_spearman: dict[float, float | None]) -> float:
    """The best-scoring weight; near-ties (within TIE_TOLERANCE) go to the higher efficiency."""
    scored = {w: s for w, s in average_spearman.items() if s is not None}
    best = max(scored.values())
    return max(w for w, s in scored.items() if s >= best - TIE_TOLERANCE)


def _split_seasons(
    seasons: list[int], tune: Sequence[int] | None, test: Sequence[int] | None
) -> tuple[list[int], list[int]]:
    """Tune on the earlier completed seasons, test on the later ones. The newest season, which
    may still be in progress, is never used to choose a weight."""
    completed = seasons[:-1] if len(seasons) > 1 else seasons
    split = max(1, math.ceil(len(completed) * 0.6))
    return list(tune or completed[:split]), list(test or completed[split:] or completed[-1:])


def _method_results(groups: list[GroupResult], methods: Sequence[str]) -> dict:
    results = {}
    for method in methods:
        per_position = {p: _summarize(groups, method, p) for p in POSITIONS}
        results[method] = {
            "average_spearman": _average_across_positions(per_position, "spearman"),
            "average_lift": _average_across_positions(per_position, "lift"),
            "positions": per_position,
        }
    return results


def run_backtest(
    warehouse_path: Path,
    *,
    now: datetime,
    tune_seasons: Sequence[int] | None = None,
    test_seasons: Sequence[int] | None = None,
) -> dict:
    """Run the backtest against a built warehouse and return a JSON-ready summary."""
    connection = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        pairs = load_pairs(connection)
    finally:
        connection.close()
    if not pairs:
        raise ValueError(
            "no ranked players with a following week to score; build the warehouse first"
        )

    tune, test = _split_seasons(
        sorted({row["season"] for row in pairs}), tune_seasons, test_seasons
    )
    methods = [method_name(w) for w in EFFICIENCY_WEIGHTS] + list(BASELINES)

    groups = {outcome: score_groups(pairs, outcome=column) for outcome, column in OUTCOMES.items()}
    results: dict[str, dict] = {}
    for outcome, outcome_groups in groups.items():
        results[outcome] = {
            "tune": _method_results([g for g in outcome_groups if g.season in set(tune)], methods),
            "test": _method_results([g for g in outcome_groups if g.season in set(test)], methods),
        }

    # Choose the weight on the tuning seasons only, using fantasy points as the outcome.
    tuning_average = {
        w: results["points"]["tune"][method_name(w)]["average_spearman"] for w in EFFICIENCY_WEIGHTS
    }
    selected = choose_weight(tuning_average)
    selected_method, current_method = method_name(selected), method_name(CURRENT_WEIGHT)

    held_out = [g for g in groups["points"] if g.season in set(test)]
    comparison = {
        method: {
            position: _paired_difference(held_out, method, "ppr_per_game", position)
            for position in POSITIONS
        }
        for method in (selected_method, current_method)
    }

    # Efficiency is noisiest early in a season, so also look at how each method does by week.
    shown = [selected_method, current_method, "ppr_per_game", "ppr_total"]
    by_week = {}
    for label, (first, last) in WEEK_BUCKETS.items():
        bucket = [g for g in held_out if first <= g.week <= last]
        by_week[label] = {
            method: _average_across_positions(
                {p: _summarize(bucket, method, p) for p in POSITIONS}, "spearman"
            )
            for method in shown
        }

    return {
        "generated_at": now.isoformat(),
        "question": "Does the rank at week N predict what a player does in week N+1?",
        "seasons": {"tune": tune, "test": test},
        "top_k": TOP_K,
        "min_pool": MIN_POOL,
        "methods": methods,
        "results": results,
        "selected_efficiency_weight": selected,
        "best_tuning_average_spearman": max(v for v in tuning_average.values() if v is not None),
        "current_efficiency_weight": CURRENT_WEIGHT,
        "selection_rule": (
            "the highest efficiency weight whose average Spearman across positions on the tuning "
            f"seasons is within {TIE_TOLERANCE} of the best (near-ties go to more efficiency)"
        ),
        "held_out_vs_ppr_per_game": comparison,
        "held_out_by_week_of_season": by_week,
    }


def summary_for_methodology(summary: dict) -> dict:
    """The few headline numbers the website's methodology page shows."""
    selected = method_name(summary["selected_efficiency_weight"])
    current = method_name(summary["current_efficiency_weight"])
    held_out = summary["results"]["points"]["test"]
    return {
        "generated_at": summary["generated_at"],
        "tuning_seasons": summary["seasons"]["tune"],
        "held_out_seasons": summary["seasons"]["test"],
        "selected_efficiency_weight": summary["selected_efficiency_weight"],
        "current_efficiency_weight": summary["current_efficiency_weight"],
        "held_out_spearman": {
            position: {
                "selected": held_out[selected]["positions"][position]["spearman"],
                "current": held_out[current]["positions"][position]["spearman"],
                "points_per_game_baseline": held_out["ppr_per_game"]["positions"][position][
                    "spearman"
                ],
            }
            for position in POSITIONS
        },
    }


def _fmt(value: float | None, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _label(method: str, selected: float, current: float) -> str:
    if method == "ppr_total":
        return "Baseline: season fantasy points"
    if method == "ppr_per_game":
        return "Baseline: fantasy points per game"
    weight = int(method.split("_")[1]) / 100
    label = f"Composite, {weight:.0%} efficiency"
    if abs(weight - selected) < 1e-9:
        label += " (chosen)"
    if abs(weight - current) < 1e-9:
        label += " (current)"
    return label


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def render_report(summary: dict) -> str:
    """A readable Markdown report of the backtest summary."""
    tune, test = summary["seasons"]["tune"], summary["seasons"]["test"]
    selected, current = summary["selected_efficiency_weight"], summary["current_efficiency_weight"]
    results = summary["results"]
    chosen_method, current_method = method_name(selected), method_name(current)

    lines = [
        "# Backtest: does rank predict next week?",
        "",
        f"Generated {summary['generated_at']}. {summary['question']}",
        "",
        f"The efficiency weight was chosen on the tuning seasons ({', '.join(map(str, tune))}) and "
        f"checked on the held-out seasons ({', '.join(map(str, test))}).",
        f"Selection rule: {summary['selection_rule']}.",
        "",
        "## How to read the numbers",
        "",
        "- **Spearman**: rank correlation between the ranking score at week N and the outcome in "
        "week N+1, averaged over every week. 0 means no relationship; 1 would be perfect. "
        "Single-game player results are very noisy, so modest values are expected.",
        "- **Lift**: extra next-week points the top-ranked players scored versus the average "
        "ranked player (top 12 QB/TE/K, top 24 RB/WR).",
        "- Only players ranked at week N who played in week N+1 are counted.",
        "- The two baselines are simple: rank by season fantasy points, or by points per game.",
        "",
        "## Next-week fantasy points (the outcome used to choose the weight)",
        "",
        "Average across positions.",
        "",
    ]
    points = results["points"]
    lines += _table(
        ["Method", "Tuning Spearman", "Tuning lift", "Held-out Spearman", "Held-out lift"],
        [
            [
                _label(m, selected, current),
                _fmt(points["tune"][m]["average_spearman"]),
                _fmt(points["tune"][m]["average_lift"], 2),
                _fmt(points["test"][m]["average_spearman"]),
                _fmt(points["test"][m]["average_lift"], 2),
            ]
            for m in summary["methods"]
        ],
    )

    epa = results["epa"]
    lines += [
        "",
        "## Next-week EPA (an efficiency-flavored outcome)",
        "",
        "Total EPA created next week. Kickers have no EPA, so this averages QB, RB, WR, and TE.",
        "",
    ]
    lines += _table(
        ["Method", "Tuning Spearman", "Held-out Spearman"],
        [
            [
                _label(m, selected, current),
                _fmt(epa["tune"][m]["average_spearman"]),
                _fmt(epa["test"][m]["average_spearman"]),
            ]
            for m in summary["methods"]
        ],
    )

    lines += [
        "",
        "## Held-out results by position (fantasy points)",
        "",
        "Standard error is over weeks. Weeks in one season are not independent, so treat it as a "
        "rough guide.",
        "",
    ]
    lines += _table(
        ["Position", "Weeks", "Chosen", "Current", "Per-game baseline"],
        [
            [
                position,
                str(points["test"][chosen_method]["positions"][position]["weeks"]),
                *[
                    f"{_fmt(entry['spearman'])} ± {_fmt(entry['spearman_se'])}"
                    for entry in (
                        points["test"][chosen_method]["positions"][position],
                        points["test"][current_method]["positions"][position],
                        points["test"]["ppr_per_game"]["positions"][position],
                    )
                ],
            ]
            for position in POSITIONS
        ],
    )

    comparison = summary["held_out_vs_ppr_per_game"]
    lines += [
        "",
        "## Composite minus the per-game baseline (held-out, Spearman, paired by week)",
        "",
        "A positive difference means the composite ranked next week's results better than simply "
        "ranking by fantasy points per game.",
        "",
    ]
    lines += _table(
        ["Position", "Chosen", "Current"],
        [
            [
                position,
                *[
                    f"{_fmt(comparison[m][position]['mean_difference'])} "
                    f"± {_fmt(comparison[m][position]['se'])}"
                    for m in (chosen_method, current_method)
                ],
            ]
            for position in POSITIONS
        ],
    )

    shown = [chosen_method, current_method, "ppr_per_game", "ppr_total"]
    lines += [
        "",
        "## Held-out Spearman by point in the season (fantasy points, average across positions)",
        "",
        "Efficiency rates rest on few plays early in a season, so the picture can change by week.",
        "",
    ]
    lines += _table(
        ["Weeks", *[_label(m, selected, current) for m in shown]],
        [
            [label, *[_fmt(values[m]) for m in shown]]
            for label, values in summary["held_out_by_week_of_season"].items()
        ],
    )
    lines.append("")
    return "\n".join(lines)
