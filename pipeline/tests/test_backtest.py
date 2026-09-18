from __future__ import annotations

import json
import math
from datetime import datetime, timezone

import duckdb
import pyarrow as pa
import pytest

from nfl_pipeline.backtest import (
    MIN_POOL,
    average_ranks,
    choose_weight,
    composite,
    mean_and_se,
    method_name,
    render_report,
    run_backtest,
    score_groups,
    spearman,
    summary_for_methodology,
    top_k_lift,
)

NOW = datetime(2026, 9, 18, 15, 30, tzinfo=timezone.utc)


# --- the statistics ------------------------------------------------------------------------------


def test_average_ranks_give_tied_values_the_average_of_their_ranks():
    assert average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    assert average_ranks([5, 5, 5]) == [2.0, 2.0, 2.0]
    assert average_ranks([3, 1, 2]) == [3.0, 1.0, 2.0]


def test_spearman_of_a_perfect_ordering_is_one_and_a_reversed_one_is_minus_one():
    assert spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_matches_the_textbook_formula():
    # rho = 1 - 6 * sum(d^2) / (n * (n^2 - 1)) = 1 - 6 * 2 / 60 = 0.8
    assert spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)


def test_spearman_only_cares_about_order_not_size():
    assert spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(
        spearman([1, 2, 3, 4], [1, 900, 20, 4000])
    )


def test_spearman_is_undefined_without_variation_or_data():
    assert spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None
    assert spearman([1, 2], [1, 2]) is None


def test_top_k_lift_is_the_top_groups_advantage_over_everyone():
    scores = [5, 4, 3, 2, 1]
    outcomes = [10, 8, 2, 2, 0]

    # top 2 average 9, everyone averages 4.4
    assert top_k_lift(scores, outcomes, list("abcde"), 2) == pytest.approx(4.6)


def test_top_k_lift_needs_more_players_than_k():
    assert top_k_lift([1, 2], [1, 2], ["a", "b"], 2) is None


def test_mean_and_standard_error():
    mean, se = mean_and_se([1, 2, 3])

    assert mean == pytest.approx(2.0)
    assert se == pytest.approx(1 / math.sqrt(3))
    assert mean_and_se([4]) == (4.0, None)
    assert mean_and_se([]) == (None, None)


def test_composite_blends_the_two_scores_and_falls_back_to_the_one_present():
    row = {"efficiency_score": 80.0, "production_score": 40.0}
    assert composite(row, 0.75) == pytest.approx(70.0)
    assert composite({"efficiency_score": None, "production_score": 40.0}, 0.75) == 40.0
    assert composite({"efficiency_score": 80.0, "production_score": None}, 0.75) == 80.0
    assert composite({"efficiency_score": None, "production_score": None}, 0.75) is None


# --- choosing the weight -------------------------------------------------------------------------


def test_the_best_weight_wins_when_it_is_clearly_ahead():
    assert choose_weight({0.0: 0.30, 0.5: 0.20, 1.0: 0.10}) == 0.0


def test_near_ties_go_to_the_higher_efficiency_weight():
    assert choose_weight({0.0: 0.294, 0.2: 0.2939, 0.4: 0.279, 1.0: 0.139}) == 0.2


def test_weights_with_no_score_are_ignored():
    assert choose_weight({0.0: None, 0.5: 0.2, 1.0: None}) == 0.5


# --- scoring groups ------------------------------------------------------------------------------


def pair(index, *, efficiency, production, outcome, season=2021, week=1, position="QB"):
    return {
        "season": season,
        "week": week,
        "position": position,
        "player_id": f"P{index:02d}",
        "efficiency_score": efficiency,
        "production_score": production,
        "ppr_points": production,
        "ppr_per_game": production,
        "next_points": outcome,
        "next_epa": None,
    }


def test_a_score_that_predicts_the_outcome_scores_higher_than_one_that_does_not():
    # Production lines up with next week's points; efficiency runs the opposite way.
    pairs = [pair(i, efficiency=100 - i * 10, production=i * 10, outcome=i) for i in range(10)]

    (group,) = score_groups(pairs, weights=(0.0, 1.0))

    assert group.spearman[method_name(0.0)] == pytest.approx(1.0)
    assert group.spearman[method_name(1.0)] == pytest.approx(-1.0)
    assert group.spearman["ppr_total"] == pytest.approx(1.0)


def test_groups_smaller_than_the_minimum_pool_are_skipped():
    pairs = [pair(i, efficiency=i, production=i, outcome=i) for i in range(MIN_POOL - 1)]

    assert score_groups(pairs, weights=(0.5,)) == []


def test_players_with_no_outcome_are_left_out():
    pairs = [pair(i, efficiency=i, production=i, outcome=i) for i in range(10)]
    pairs.append(pair(99, efficiency=5, production=5, outcome=None))

    (group,) = score_groups(pairs, weights=(0.5,))

    assert group.spearman[method_name(0.5)] == pytest.approx(1.0)  # the missing outcome was ignored


# --- the full backtest against a small warehouse --------------------------------------------


def build_warehouse(path, seasons=(2021, 2022, 2023, 2024), weeks=(1, 2, 3)):
    """Ten quarterbacks a week. Production predicts next week's points; efficiency is constant."""
    rankings, weekly, stats = [], [], []
    for season in seasons:
        for week in weeks:
            for i in range(1, 11):
                rankings.append(
                    {
                        "season": season, "week": week, "position_group": "QB",
                        "player_id": f"Q{i:02d}", "is_qualified": True,
                        "efficiency_score": 50.0, "production_score": i * 10.0,
                        "ppr_points": i * 10.0 * week, "ppr_per_game": i * 10.0,
                    }
                )  # fmt: skip
                weekly.append(
                    {
                        "season": season, "week": week, "season_type": "REG",
                        "player_id": f"Q{i:02d}", "position_group": "QB",
                        "fantasy_points_scored": float(i),
                    }
                )  # fmt: skip
                stats.append(
                    {
                        "season": season, "week": week, "player_id": f"Q{i:02d}",
                        "passing_epa": float(i), "rushing_epa": 0.0, "receiving_epa": 0.0,
                    }
                )  # fmt: skip
    connection = duckdb.connect(str(path))
    for name, rows in (
        ("mart_rankings", rankings),
        ("int_weekly_fantasy_points", weekly),
        ("fct_player_week", stats),
    ):
        connection.register("staged", pa.Table.from_pylist(rows))
        connection.execute(f"create table {name} as select * from staged")
        connection.unregister("staged")
    connection.close()
    return path


@pytest.fixture
def backtest_warehouse(tmp_path):
    return build_warehouse(tmp_path / "w.duckdb")


def test_the_newest_season_is_never_used_to_choose_the_weight(backtest_warehouse):
    summary = run_backtest(backtest_warehouse, now=NOW)

    # 2021-2023 are complete; 60% of them tune, the rest are held out. 2024 may be in progress.
    assert summary["seasons"] == {"tune": [2021, 2022], "test": [2023]}


def test_the_weight_is_chosen_on_tuning_seasons_and_confirmed_on_held_out_ones(backtest_warehouse):
    summary = run_backtest(backtest_warehouse, now=NOW)

    # Constant efficiency leaves production to decide the order, so every weight below 100%
    # ties at a perfect score and the near-tie rule picks the highest of them.
    assert summary["selected_efficiency_weight"] == 0.8
    held_out = summary["results"]["points"]["test"][method_name(0.8)]
    assert held_out["positions"]["QB"]["spearman"] == pytest.approx(1.0)
    assert held_out["positions"]["QB"]["weeks"] == 2  # weeks 1 and 2 have a following week


def test_a_constant_score_has_no_rank_correlation(backtest_warehouse):
    summary = run_backtest(backtest_warehouse, now=NOW)

    assert (
        summary["results"]["points"]["test"][method_name(1.0)]["positions"]["QB"]["spearman"]
        is None
    )


def test_positions_with_no_data_are_reported_as_empty_not_as_errors(backtest_warehouse):
    summary = run_backtest(backtest_warehouse, now=NOW)

    rb = summary["results"]["points"]["test"][method_name(0.8)]["positions"]["RB"]
    assert rb["weeks"] == 0 and rb["spearman"] is None


def test_epa_is_scored_as_a_second_outcome(backtest_warehouse):
    summary = run_backtest(backtest_warehouse, now=NOW)

    epa = summary["results"]["epa"]["test"][method_name(0.8)]["positions"]["QB"]
    assert epa["spearman"] == pytest.approx(1.0)


def test_the_report_renders_and_names_the_chosen_and_current_settings(backtest_warehouse):
    report = render_report(run_backtest(backtest_warehouse, now=NOW))

    assert "# Backtest" in report
    assert "(chosen)" in report and "(current)" in report
    assert "Baseline: fantasy points per game" in report


def test_the_methodology_summary_carries_the_headline_numbers(backtest_warehouse):
    summary = run_backtest(backtest_warehouse, now=NOW)

    headline = summary_for_methodology(summary)

    assert headline["selected_efficiency_weight"] == 0.8
    assert headline["held_out_seasons"] == [2023]
    assert headline["held_out_spearman"]["QB"]["selected"] == pytest.approx(1.0)
    json.dumps(headline)  # must be JSON-serializable for meta files


def test_tables_with_no_rows_are_reported_clearly(backtest_warehouse):
    connection = duckdb.connect(str(backtest_warehouse))
    for table in ("mart_rankings", "int_weekly_fantasy_points", "fct_player_week"):
        connection.execute(f"delete from {table}")
    connection.close()

    with pytest.raises(ValueError, match="no ranked players"):
        run_backtest(backtest_warehouse, now=NOW)


def test_a_warehouse_that_was_never_built_raises_a_database_error(tmp_path):
    duckdb.connect(str(tmp_path / "unbuilt.duckdb")).close()

    with pytest.raises(duckdb.Error):
        run_backtest(tmp_path / "unbuilt.duckdb", now=NOW)
