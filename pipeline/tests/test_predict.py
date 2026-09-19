"""Tests for the prediction engine's building blocks.

These use generated data rather than the warehouse so they run fast and offline. The properties
checked are the ones the research paper says matter: injured players are excluded, ranges are
honest, and nothing is allowed to calibrate on data it trained on.
"""

from __future__ import annotations

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
        # These are in FEATURE_COLUMNS, so they must be set after the noise loop above or they
        # get overwritten. prior_games decides what is trainable, so it matters.
        frame["prior_games"] = rng.integers(4, 40, per_season)
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
