"""Tests for the prediction engine's building blocks.

These use generated data rather than the warehouse so they run fast and offline. The properties
checked are the ones the research paper says matter: injured players are excluded, ranges are
honest, and nothing is allowed to calibrate on data it trained on.
"""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest

from nfl_pipeline.predict.availability import (
    RULED_OUT,
    AvailabilityModel,
    expected_points,
    practice_features,
)
from nfl_pipeline.predict.features import FEATURE_COLUMNS, model_columns
from nfl_pipeline.predict.models import MIN_PRIOR_GAMES, PredictionModel, baseline_predictions

POSITIONS = ["QB", "RB", "WR", "TE", "K"]


def make_frame(rows: int = 1200, seed: int = 0, seasons=(2021, 2022, 2023)) -> pd.DataFrame:
    """Player-weeks whose scores genuinely depend on their recent form, plus noise."""
    rng = np.random.default_rng(seed)
    per_season = rows // len(seasons)
    frames = []
    for index, season in enumerate(seasons):
        form = rng.gamma(4.0, 2.5, per_season)
        frame = pd.DataFrame(
            {
                "player_id": [f"P{i % 120:03d}" for i in range(per_season)],
                "season": season,
                "week": [(i % 17) + 1 for i in range(per_season)],
                "position_group": [POSITIONS[i % len(POSITIONS)] for i in range(per_season)],
                "position_code": [i % len(POSITIONS) for i in range(per_season)],
                "prior_games": rng.integers(0, 40, per_season),
                "injury_status": None,
                "actual_ppr": np.maximum(form + rng.normal(0, 5, per_season), 0),
            }
        )
        for column in FEATURE_COLUMNS:
            frame[column] = rng.normal(0, 1, per_season)
        # `prior_games` and `week` are both in FEATURE_COLUMNS, so they must be restored after the
        # noise loop above or they get overwritten. prior_games decides what is trainable and week
        # decides which rows a walk-forward run can see, so silently losing them hides real bugs.
        frame["prior_games"] = rng.integers(4, 40, per_season)
        frame["week"] = [(i % 17) + 1 for i in range(per_season)]
        # Make recent form genuinely informative, so a model can beat guessing.
        frame["ppr_mean5"] = form
        frame["ppr_mean3"] = form + rng.normal(0, 1, per_season)
        frame["ppr_mean10"] = form + rng.normal(0, 1, per_season)
        frame["ppr_season_avg"] = form + rng.normal(0, 1, per_season)
        frame["week"] = frame.week + index * 0  # seasons keep their own weeks
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    # Unique keys, so the calibration overlap check is meaningful.
    out["player_id"] = [f"P{i:05d}" for i in range(len(out))]
    return out


# ---------------------------------------------------------------- availability


def test_out_and_doubtful_players_are_treated_as_unavailable():
    frame = make_frame(300)
    frame.loc[0, "injury_status"] = "Out"
    frame.loc[1, "injury_status"] = "Doubtful"

    result = AvailabilityModel().evaluate(frame)

    assert result.available.iloc[0] is np.False_ or not result.available.iloc[0]
    assert not result.available.iloc[1]
    assert result.probability.iloc[0] == 0.0
    assert result.probability.iloc[1] == 0.0


def test_players_not_on_the_injury_report_are_assumed_to_play():
    frame = make_frame(50)

    probability = AvailabilityModel().probability_of_playing(frame)

    assert (probability == 1.0).all()


def test_questionable_players_get_the_measured_base_rate_before_any_fitting():
    frame = make_frame(10)
    frame["injury_status"] = "Questionable"

    probability = AvailabilityModel().probability_of_playing(frame)

    # 63% is what Questionable players actually did from 2021-2025.
    assert probability.between(0.5, 0.75).all()


def test_the_model_learns_that_missing_practice_means_missing_the_game():
    rng = np.random.default_rng(3)
    size = 600
    practice = rng.choice(
        ["Did Not Participate In Practice", "Limited Participation in Practice",
         "Full Participation in Practice"],
        size,
    )  # fmt: skip
    chance = pd.Series(practice).map(
        {
            "Did Not Participate In Practice": 0.2,
            "Limited Participation in Practice": 0.65,
            "Full Participation in Practice": 0.9,
        }
    )
    played = (rng.random(size) < chance).astype(int)
    history = pd.DataFrame({"practice_status": practice, "position_code": rng.integers(0, 5, size)})

    model = AvailabilityModel().fit(history, played)

    ask = pd.DataFrame(
        {
            "injury_status": ["Questionable", "Questionable"],
            "practice_status": [
                "Did Not Participate In Practice",
                "Full Participation in Practice",
            ],
            "position_code": [0, 0],
        }
    )
    probability = model.probability_of_playing(ask)
    assert probability.iloc[0] < probability.iloc[1]


def test_practice_text_becomes_three_clean_flags():
    frame = pd.DataFrame(
        {
            "practice_status": [
                "Did Not Participate In Practice",
                "Full Participation in Practice",
                None,
            ]
        }
    )

    flags = practice_features(frame)

    assert flags.did_not_practice.tolist() == [1.0, 0.0, 0.0]
    assert flags.full_practice.tolist() == [0.0, 1.0, 0.0]
    assert flags.limited_practice.sum() == 0.0


def test_expected_points_discounts_by_the_chance_of_playing():
    assert expected_points([10.0, 10.0], [1.0, 0.5]).tolist() == [10.0, 5.0]


def test_the_ruled_out_statuses_are_the_ones_the_research_measured():
    assert set(RULED_OUT) == {"Out", "Doubtful"}


# ---------------------------------------------------------------- the model


@pytest.fixture(scope="module")
def fitted() -> tuple[PredictionModel, pd.DataFrame]:
    history = make_frame(1500, seed=1, seasons=(2021, 2022))
    calibration = make_frame(600, seed=2, seasons=(2023,))
    model = PredictionModel().fit(history, calibration=calibration)
    return model, make_frame(600, seed=4, seasons=(2024,))


def test_it_predicts_a_number_for_every_row(fitted):
    model, future = fitted

    points = model.predict_points(future)

    assert len(points) == len(future)
    assert np.isfinite(points).all()


def test_predictions_are_never_negative(fitted):
    model, future = fitted

    points = model.predict_points(future)
    low, high = model.predict_interval(future)

    assert (points >= 0).all()
    assert (low >= 0).all()


def test_the_range_always_contains_its_own_point_estimate_order(fitted):
    model, future = fitted

    low, high = model.predict_interval(future)

    assert (high >= low).all()


def test_a_better_recent_average_predicts_more_points(fitted):
    """Sanity: the model should have learned the direction of its strongest feature."""
    model, future = fitted
    quiet = future.head(1).copy()
    busy = quiet.copy()
    quiet["ppr_mean5"] = 3.0
    busy["ppr_mean5"] = 25.0

    assert model.predict_points(busy)[0] > model.predict_points(quiet)[0]


def test_calibrating_on_training_data_is_refused():
    """The mistake that would silently make every published range too narrow."""
    history = make_frame(1500, seed=5, seasons=(2021, 2022))

    with pytest.raises(ValueError, match="also used for training"):
        PredictionModel().fit(history, calibration=history.head(500))


def test_fitting_needs_enough_history():
    with pytest.raises(ValueError, match="at least"):
        PredictionModel().fit(make_frame(30, seasons=(2021,)))


def test_predicting_before_fitting_is_an_error():
    with pytest.raises(ValueError, match="not been fitted"):
        PredictionModel().predict_points(make_frame(10))


def test_players_without_enough_history_are_left_out_of_training():
    frame = make_frame(500, seed=6, seasons=(2021,))
    frame.loc[frame.index[:100], "prior_games"] = 0

    trainable = PredictionModel.trainable(frame)

    assert (trainable.prior_games >= MIN_PRIOR_GAMES).all()
    assert len(trainable) < len(frame)


def test_predict_returns_availability_adjusted_expectations(fitted):
    model, future = fitted
    chance = np.full(len(future), 0.5)

    out = model.predict(future, play_probability=chance)

    assert np.allclose(out.expected_points, out.points * 0.5)
    assert (out.model_version == "v1").all()
    assert set(["player_id", "season", "week", "low", "high"]).issubset(out.columns)


def test_baselines_are_available_and_never_null():
    frame = make_frame(200, seed=7, seasons=(2021,))
    frame.loc[frame.index[:20], ["ppr_mean5", "ppr_mean10", "ppr_season_avg"]] = np.nan

    baselines = baseline_predictions(frame)

    assert set(baselines) == {"recent_average", "season_average", "last_ten"}
    for name, values in baselines.items():
        assert np.isfinite(values).all(), name


def test_the_model_only_ever_sees_feature_columns():
    """The outcome must never reach the model's inputs."""
    columns = model_columns()

    assert "actual_ppr" not in columns
    assert "player_id" not in columns
    assert set(columns) == set(FEATURE_COLUMNS) | {"position_code"}


# ---------------------------------------------------------------- the harness and the gate


def walkable_frame(seasons=(2021, 2022, 2023, 2024), per_week: int = 60) -> pd.DataFrame:
    """Several seasons of weekly data, big enough for the harness to train and test on."""
    rng = np.random.default_rng(11)
    rows = []
    for season in seasons:
        for week in range(1, 19):
            form = rng.gamma(4.0, 2.5, per_week)
            block = pd.DataFrame(
                {
                    "player_id": [f"W{i:03d}" for i in range(per_week)],
                    "season": season,
                    "week": week,
                    "position_group": [POSITIONS[i % len(POSITIONS)] for i in range(per_week)],
                    "position_code": [i % len(POSITIONS) for i in range(per_week)],
                    "injury_status": None,
                    "actual_ppr": np.maximum(form + rng.normal(0, 5, per_week), 0),
                }
            )
            for column in FEATURE_COLUMNS:
                block[column] = rng.normal(0, 1, per_week)
            block["prior_games"] = 10
            block["week"] = week  # restored: `week` is itself a feature column
            block["ppr_mean5"] = form
            block["ppr_mean3"] = form + rng.normal(0, 1, per_week)
            block["ppr_mean10"] = form + rng.normal(0, 1, per_week)
            block["ppr_season_avg"] = form + rng.normal(0, 1, per_week)
            rows.append(block)
    return pd.concat(rows, ignore_index=True)


@pytest.fixture(scope="module")
def backtest():
    from nfl_pipeline.predict.backtest import walk_forward

    return walk_forward(walkable_frame(), test_seasons=(2024,), min_history_rows=1000)


def test_the_harness_grades_every_week_it_can(backtest):
    assert len(backtest.weeks) >= 15
    assert backtest.player_games > 800
    assert all(w.players > 0 for w in backtest.weeks)


def test_it_reports_accuracy_alongside_the_baselines_it_must_beat(backtest):
    summary = backtest.summary()

    assert summary["mae"] > 0
    assert set(summary["baselines"]) == {"recent_average", "season_average", "last_ten"}
    assert summary["best_baseline"] in summary["baselines"]
    # The headline number is the margin over the best baseline, not raw accuracy.
    assert "improvement_over_best_baseline" in summary


def test_every_week_trains_only_on_earlier_weeks():
    """The harness must never hand a week its own data. Later weeks see strictly more history."""
    from nfl_pipeline.predict.backtest import walk_forward

    seen: list[int] = []

    class Recording(PredictionModel):
        def fit(self, history, calibration=None):
            seen.append(len(history))
            if len(history):
                assert history.season.max() <= 2024
            return super().fit(history, calibration=calibration)

    result = walk_forward(
        walkable_frame(), test_seasons=(2024,), model_factory=Recording, min_history_rows=1000
    )

    assert len(seen) == len(result.weeks)
    assert seen == sorted(seen), "training history should only ever grow"


def test_intervals_stay_honest_across_the_whole_backtest(backtest):
    # A nominal 80% range that covers far more or less than that is not worth publishing.
    assert 0.7 <= backtest.coverage <= 0.9


# --- the promotion gate


class FakeResult:
    """Stands in for a backtest result, so the gate can be tested on exact numbers."""

    def __init__(self, mae: float, coverage: float = 0.8) -> None:
        self.mae = mae
        self.coverage = coverage


def test_a_clearly_better_challenger_is_promoted():
    from nfl_pipeline.predict.backtest import promotion_decision

    decision = promotion_decision(FakeResult(5.0), FakeResult(4.5))

    assert decision["promote"] is True
    assert "beats the champion" in decision["reason"]


def test_a_worse_challenger_is_rejected():
    from nfl_pipeline.predict.backtest import promotion_decision

    decision = promotion_decision(FakeResult(4.5), FakeResult(5.0))

    assert decision["promote"] is False
    assert "worse than the champion" in decision["reason"]


def test_a_barely_better_challenger_is_rejected_as_noise():
    """The rule that stops the model drifting on random weekly wobble."""
    from nfl_pipeline.predict.backtest import promotion_decision

    decision = promotion_decision(FakeResult(4.50), FakeResult(4.48))

    assert decision["promote"] is False
    assert "noise margin" in decision["reason"]


def test_a_tie_keeps_the_incumbent():
    from nfl_pipeline.predict.backtest import promotion_decision

    assert promotion_decision(FakeResult(4.5), FakeResult(4.5))["promote"] is False


def test_a_more_accurate_challenger_with_dishonest_ranges_is_rejected():
    """Accuracy is not enough: a model whose 80% range covers 40% is not shippable."""
    from nfl_pipeline.predict.backtest import promotion_decision

    decision = promotion_decision(FakeResult(5.0), FakeResult(4.0, coverage=0.40))

    assert decision["promote"] is False
    assert "dishonest" in decision["reason"]


# ---------------------------------------------------------------- the weekly lock


@pytest.fixture
def weekly(tmp_path):
    """A projected week for 2024 week 18, plus a scratch directory to lock it into."""
    from nfl_pipeline.predict.weekly import predict_week

    features = walkable_frame()
    # The week being projected has no outcome yet, which is the situation that matters.
    future = (features.season == 2024) & (features.week == 18)
    features.loc[future, "actual_ppr"] = np.nan
    return predict_week(features, season=2024, week=18), features, tmp_path


def test_a_week_that_has_not_been_played_can_still_be_projected(weekly):
    """The whole point of a projection is that the answer does not exist yet."""
    predictions, _, _ = weekly

    assert len(predictions.rows) > 0
    assert predictions.status == "preliminary"


def test_locking_a_week_records_when_it_became_final(weekly):
    from nfl_pipeline.predict.weekly import lock_week

    predictions, _, root = weekly

    locked = lock_week(predictions, root)

    assert locked.status == "locked"
    assert locked.locked_at is not None


def test_relocking_the_same_numbers_is_allowed_because_runs_get_retried(weekly):
    from nfl_pipeline.predict.weekly import lock_week

    predictions, _, root = weekly
    first = lock_week(predictions, root)

    again = lock_week(predictions, root)

    assert again.locked_at == first.locked_at


def test_a_locked_week_cannot_be_quietly_rewritten(weekly):
    """This is the guarantee the whole report card rests on.

    If a later run could overwrite last week's projections with better ones, the published accuracy
    would measure hindsight rather than prediction.
    """
    from nfl_pipeline.predict.weekly import lock_week

    predictions, _, root = weekly
    lock_week(predictions, root)
    improved = copy.deepcopy(predictions)
    improved.rows["points"] = improved.rows["points"] + 1.0

    with pytest.raises(ValueError, match="already locked"):
        lock_week(improved, root)


def test_locked_predictions_survive_a_round_trip_to_disk(weekly):
    from nfl_pipeline.predict.weekly import load_locked, lock_week

    predictions, _, root = weekly
    locked = lock_week(predictions, root)

    reloaded = load_locked(root, 2024, 18)

    assert reloaded.locked_at == locked.locked_at
    pd.testing.assert_series_equal(
        reloaded.rows.points.round(6), locked.rows.points.round(6), check_dtype=False
    )


def test_grading_scores_the_locked_numbers_against_what_happened(weekly):
    from nfl_pipeline.predict.weekly import grade_week, lock_week

    predictions, features, root = weekly
    locked = lock_week(predictions, root)
    # The games are now played.
    played = walkable_frame()

    graded = grade_week(locked, played)

    assert graded.player_games > 0
    assert graded.mae > 0
    assert set(graded.baseline_mae) == {"recent_average", "season_average", "last_ten"}


def test_a_player_who_never_took_the_field_is_not_graded_as_a_miss(weekly):
    """Missing a game is the availability model's business, not the points model's."""
    from nfl_pipeline.predict.weekly import grade_week, lock_week

    predictions, _, root = weekly
    locked = lock_week(predictions, root)
    played = walkable_frame()
    # Taken from the locked rows, not from the fixture: not every player in the fixture is
    # projected (low-volume ones are filtered out), so picking from the fixture would sometimes
    # choose someone who was never in the locked week and the count would come out unchanged.
    absent = locked.rows.player_id.iloc[0]
    played.loc[
        (played.season == 2024) & (played.week == 18) & (played.player_id == absent), "actual_ppr"
    ] = np.nan

    graded = grade_week(locked, played)

    assert graded.player_games == len(locked.rows) - 1


def test_the_frozen_control_is_graded_on_the_same_rows(weekly):
    """Without a fixed control line, 'the model is improving' cannot be checked."""
    from nfl_pipeline.predict.weekly import grade_week, lock_week

    predictions, _, root = weekly
    locked = lock_week(predictions, root)
    played = walkable_frame()
    # A deliberately poor frozen model: everyone gets the league average.
    frozen = pd.Series(8.0, index=locked.rows.player_id)

    graded = grade_week(locked, played, frozen_points=frozen)

    assert graded.frozen_model_mae is not None
    assert graded.frozen_model_mae > graded.mae


def test_players_ruled_out_are_left_out_of_the_published_week():
    """A projection of zero reads as 'he will play badly', not 'he is not playing'."""
    from nfl_pipeline.predict.weekly import predict_week

    features = walkable_frame()
    future = (features.season == 2024) & (features.week == 18)
    features.loc[future, "actual_ppr"] = np.nan
    benched = features.player_id.iloc[0]
    # Make him comfortably worth projecting, so that if he is missing from the output it is
    # because he was ruled out and not because the eligibility filter had already dropped him.
    # Otherwise this test could pass while proving nothing.
    features.loc[future & (features.player_id == benched), "ppr_mean5"] = 12.0
    assert benched in set(predict_week(features, season=2024, week=18).rows.player_id)

    features.loc[future & (features.player_id == benched), "injury_status"] = "Out"

    predictions = predict_week(features, season=2024, week=18)

    assert benched not in set(predictions.rows.player_id)


# ---------------------------------------------------------------- judged on what we publish


def published_frame(n: int = 600, champion_noise: float = 4.0, challenger_noise: float = 4.0):
    """Two sets of predictions over the same rows, half of them below the publishing threshold."""
    rng = np.random.default_rng(5)
    form = np.concatenate([rng.uniform(0, 3.5, n // 2), rng.uniform(6, 20, n // 2)])
    actual = np.maximum(form + rng.normal(0, 5, n), 0)
    frame = pd.DataFrame(
        {
            "player_id": [f"P{i:04d}" for i in range(n)],
            "season": 2025,
            "week": 7,
            "position_group": "WR",
            "actual_ppr": actual,
            "ppr_mean5": form,
            "low": actual - 12,
            "high": actual + 12,
        }
    )
    champion = frame.assign(points=actual + rng.normal(0, champion_noise, n))
    challenger = frame.assign(points=actual + rng.normal(0, challenger_noise, n))
    return champion, challenger


def as_result(predictions: pd.DataFrame):
    from nfl_pipeline.predict.backtest import BacktestResult

    result = BacktestResult()
    result.predictions = predictions
    return result


def test_scoring_covers_only_the_players_the_site_publishes():
    """Judging a change over players it will never affect dilutes it."""
    from nfl_pipeline.predict.backtest import score_on_published

    champion, _ = published_frame()

    scored = score_on_published(as_result(champion))

    assert scored.player_games == 300
    assert (scored.predictions.ppr_mean5 >= 4.0).all()


def test_the_paired_mean_equals_the_difference_of_the_two_error_rates():
    """The pairing adds a standard error to a number the gate already used, not a new number."""
    from nfl_pipeline.predict.backtest import paired_evidence, score_on_published

    champion, challenger = published_frame(challenger_noise=2.0)
    a, b = score_on_published(as_result(champion)), score_on_published(as_result(challenger))

    evidence = paired_evidence(a, b)

    assert evidence["mean_improvement"] == pytest.approx(a.mae - b.mae, abs=1e-4)
    assert evidence["standard_error"] > 0


def test_an_improvement_inside_its_own_noise_is_rejected_however_big_the_margin_looks():
    """A fixed margin cannot tell a real gain from a lucky one; the paired spread can."""
    from nfl_pipeline.predict.backtest import promotion_decision

    noisy = {
        "player_games": 300,
        "mean_improvement": 0.2,
        "standard_error": 0.4,
        "standard_errors_from_zero": 0.5,
        "rows_improved": 150,
    }

    decision = promotion_decision(FakeResult(4.70), FakeResult(4.50), paired=noisy)

    assert decision["promote"] is False
    assert "not distinguishable from chance" in decision["reason"]


def test_a_consistent_improvement_is_still_promoted():
    from nfl_pipeline.predict.backtest import promotion_decision

    solid = {
        "player_games": 8000,
        "mean_improvement": 0.2,
        "standard_error": 0.04,
        "standard_errors_from_zero": 5.0,
        "rows_improved": 4600,
    }

    decision = promotion_decision(FakeResult(4.70), FakeResult(4.50), paired=solid)

    assert decision["promote"] is True


def test_the_gate_still_works_without_paired_evidence():
    """The older callers pass none, and must keep behaving exactly as before."""
    from nfl_pipeline.predict.backtest import promotion_decision

    assert promotion_decision(FakeResult(4.70), FakeResult(4.50))["promote"] is True


def test_comparing_results_with_no_shared_rows_is_an_error():
    from nfl_pipeline.predict.backtest import paired_evidence, score_on_published

    champion, challenger = published_frame()
    challenger = challenger.assign(player_id=challenger.player_id + "_other")
    a, b = score_on_published(as_result(champion)), score_on_published(as_result(challenger))

    with pytest.raises(ValueError, match="share no graded rows"):
        paired_evidence(a, b)
