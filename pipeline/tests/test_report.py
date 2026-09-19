"""The Report card must describe the numbers it is given, including when they are bad."""

from __future__ import annotations

import pytest

from nfl_pipeline.contract import GradedWeek
from nfl_pipeline.predict.report import build_accuracy_file, combine, verdict


def week(
    number: int,
    mae: float,
    baseline: float = 5.40,
    coverage: float = 0.80,
    frozen: float | None = None,
    players: int = 200,
) -> GradedWeek:
    return GradedWeek(
        season=2025,
        week=number,
        player_games=players,
        mae=mae,
        rmse=mae * 1.4,
        interval_coverage=coverage,
        baseline_mae={"recent_average": baseline, "season_average": baseline + 0.2},
        frozen_model_mae=frozen,
    )


def test_a_busy_week_counts_for_more_than_a_quiet_one():
    """Pooling by player-games, not averaging weeks, is the difference between honest and tidy."""
    pooled = combine([week(1, mae=4.0, players=400), week(2, mae=6.0, players=100)])

    assert pooled.player_games == 500
    assert pooled.mae == pytest.approx(4.4)


def test_it_says_plainly_when_the_model_is_losing_to_a_simple_average():
    weeks = [week(n, mae=5.60, baseline=5.40) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "not currently earning its place" in text


def test_a_margin_inside_the_noise_band_is_not_dressed_up_as_a_win():
    weeks = [week(n, mae=5.34, baseline=5.40) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "inside the margin this project treats as noise" in text


def test_a_real_margin_is_stated_as_one():
    weeks = [week(n, mae=5.20, baseline=5.40) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "ahead by 0.20 points per game" in text


def test_accuracy_is_always_reported_next_to_its_player_count():
    """Mean error depends on which players are included, so the number alone is misleading."""
    weeks = [week(n, mae=5.20) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "1,200 player-games" in text


def test_ranges_that_are_too_narrow_are_called_out():
    weeks = [week(n, mae=5.20, coverage=0.62) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "too narrow" in text


def test_the_learning_claim_is_only_made_when_the_control_supports_it():
    weeks = [week(n, mae=5.20, frozen=5.50) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "beating a model frozen before the season by 0.30" in text


def test_being_level_with_the_frozen_model_is_reported_as_no_improvement():
    weeks = [week(n, mae=5.20, frozen=5.21) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "nothing added this year has made a measurable difference" in text


def test_getting_worse_than_the_frozen_model_is_reported_too():
    weeks = [week(n, mae=5.50, frozen=5.20) for n in range(1, 7)]

    text = verdict(weeks, combine(weeks))

    assert "worse than a model frozen before the season" in text


def test_a_handful_of_weeks_is_not_read_as_a_trend():
    weeks = [week(n, mae=5.20, frozen=5.90) for n in range(1, 3)]

    text = verdict(weeks, combine(weeks))

    assert "too few to read anything into" in text


def test_no_graded_games_means_no_claims():
    assert "nothing to report" in verdict([], None)


def test_the_published_file_carries_the_weeks_in_order():
    accuracy = build_accuracy_file(2025, [week(3, 5.2), week(1, 5.4), week(2, 5.3)])

    assert [w.week for w in accuracy.weeks] == [1, 2, 3]
    assert accuracy.season_to_date.player_games == 600
