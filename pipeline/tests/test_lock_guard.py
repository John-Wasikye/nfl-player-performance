"""The kickoff guard: a forecast may only be locked while it is still a forecast."""

from datetime import datetime, timedelta, timezone

import duckdb
import pandas as pd
import pytest

from nfl_pipeline import cli
from nfl_pipeline.config import Settings
from nfl_pipeline.predict import run as run_module
from nfl_pipeline.predict.kickoff import first_kickoff_utc, lock_state
from nfl_pipeline.predict.run import PredictionError, run_predictions
from nfl_pipeline.predict.weekly import LOCKED_COLUMNS, WeeklyPredictions, load_locked
from nfl_pipeline.storage import LocalStorage

UTC = timezone.utc
# 2026-10-11 is a Sunday. 13:00 Eastern is 17:00 UTC in summer, which the guard reads as 17:00 UTC.
SUNDAY_KICKOFF = datetime(2026, 10, 11, 13, 0)
SUNDAY_KICKOFF_UTC = datetime(2026, 10, 11, 17, 0, tzinfo=UTC)


def make_schedule(path, games):
    connection = duckdb.connect(str(path))
    connection.execute(
        "create table stg_schedules (season integer, week integer, game_type varchar, "
        "kickoff_et timestamp, game_date date)"
    )
    for season, week, game_type, kickoff, day in games:
        connection.execute(
            "insert into stg_schedules values (?, ?, ?, ?, ?)",
            [season, week, game_type, kickoff, day],
        )
    connection.close()


# ---------------------------------------------------------------- the clock


@pytest.mark.parametrize(
    "hours_before, expected",
    [
        (48, "wait"),
        (24.5, "wait"),
        (24, "lock"),
        (6, "lock"),
        (0.51, "lock"),
        (0.49, "missed"),
        (0, "missed"),
        (-3, "missed"),
    ],
)
def test_the_lock_window_opens_a_day_out_and_closes_half_an_hour_before(hours_before, expected):
    now = SUNDAY_KICKOFF_UTC - timedelta(hours=hours_before)

    assert lock_state(SUNDAY_KICKOFF_UTC, now) == expected


def test_an_unknown_kickoff_is_never_lockable():
    assert lock_state(None, SUNDAY_KICKOFF_UTC) == "unknown"


def test_a_naive_now_is_read_as_utc_rather_than_crashing():
    assert lock_state(SUNDAY_KICKOFF_UTC, datetime(2026, 10, 11, 10, 0)) == "lock"


# ---------------------------------------------------------------- reading the schedule


def test_the_first_kickoff_is_the_earliest_game_of_the_week(tmp_path):
    warehouse = tmp_path / "w.duckdb"
    make_schedule(
        warehouse,
        [
            (2026, 5, "REG", datetime(2026, 10, 11, 16, 25), datetime(2026, 10, 11)),
            (2026, 5, "REG", datetime(2026, 10, 9, 20, 15), datetime(2026, 10, 9)),
            (2026, 5, "REG", SUNDAY_KICKOFF, datetime(2026, 10, 11)),
            (2026, 6, "REG", datetime(2026, 10, 1, 13, 0), datetime(2026, 10, 1)),
        ],
    )

    assert first_kickoff_utc(warehouse, 2026, 5) == datetime(2026, 10, 10, 0, 15, tzinfo=UTC)


def test_the_estimate_errs_toward_an_earlier_kickoff_in_winter(tmp_path):
    """Eastern is UTC-5 in winter, so 13:00 is really 18:00 UTC; the guard says 17:00."""
    warehouse = tmp_path / "w.duckdb"
    make_schedule(
        warehouse,
        [(2026, 12, "REG", datetime(2026, 12, 6, 13, 0), datetime(2026, 12, 6))],
    )

    guessed = first_kickoff_utc(warehouse, 2026, 12)

    assert guessed == datetime(2026, 12, 6, 17, 0, tzinfo=UTC)
    assert guessed < datetime(2026, 12, 6, 18, 0, tzinfo=UTC)


def test_a_game_with_only_a_date_is_assumed_to_start_at_the_beginning_of_that_day(tmp_path):
    warehouse = tmp_path / "w.duckdb"
    make_schedule(warehouse, [(2026, 5, "REG", None, datetime(2026, 10, 11))])

    assert first_kickoff_utc(warehouse, 2026, 5) == datetime(2026, 10, 11, 4, 0, tzinfo=UTC)


def test_one_game_with_no_time_and_no_date_makes_the_whole_week_unknowable(tmp_path):
    warehouse = tmp_path / "w.duckdb"
    make_schedule(
        warehouse,
        [
            (2026, 5, "REG", SUNDAY_KICKOFF, datetime(2026, 10, 11)),
            (2026, 5, "REG", None, None),
        ],
    )

    assert first_kickoff_utc(warehouse, 2026, 5) is None


def test_a_week_with_no_regular_season_games_is_unknowable(tmp_path):
    warehouse = tmp_path / "w.duckdb"
    make_schedule(warehouse, [(2026, 5, "POST", SUNDAY_KICKOFF, datetime(2026, 10, 11))])

    assert first_kickoff_utc(warehouse, 2026, 5) is None


# ---------------------------------------------------------------- the run


def projection(points: float) -> WeeklyPredictions:
    rows = pd.DataFrame(
        {
            "player_id": ["P1", "P2"],
            "season": 2026,
            "week": 5,
            "position_group": "QB",
            "points": [points, points + 1],
            "low": [points - 5, points - 4],
            "high": [points + 5, points + 6],
            "probability_of_playing": 1.0,
            "expected_points": [points, points + 1],
            "model_version": "test",
        }
    )[LOCKED_COLUMNS]
    return WeeklyPredictions(
        season=2026,
        week=5,
        generated_at="2026-10-10T12:00:00+00:00",
        model_version="test",
        rows=rows,
        locked_at=None,
    )


@pytest.fixture
def world(tmp_path, monkeypatch):
    warehouse = tmp_path / "w.duckdb"
    make_schedule(warehouse, [(2026, 5, "REG", SUNDAY_KICKOFF, datetime(2026, 10, 11))])
    features = pd.DataFrame(
        {
            "player_id": ["P1", "P2"],
            "season": 2026,
            "week": 5,
            "team": "AAA",
            "opponent_team": "BBB",
            "is_home": True,
            "injury_status": None,
            "actual_ppr": float("nan"),
            "ppr_mean5": 8.0,
            "ppr_mean10": 8.0,
            "ppr_season_avg": 8.0,
        }
    )
    projected = {"points": 10.0, "calls": 0}

    def fake_predict(_features, _season, _week):
        projected["calls"] += 1
        return projection(projected["points"])

    monkeypatch.setattr(run_module, "load_features", lambda _path: features)
    monkeypatch.setattr(run_module, "predict_week", fake_predict)
    monkeypatch.setattr(
        run_module,
        "_player_details",
        lambda _path: pd.DataFrame({"player_id": ["P1", "P2"], "display_name": ["One", "Two"]}),
    )
    settings = Settings(warehouse_path=warehouse)
    return settings, LocalStorage(tmp_path / "site"), LocalStorage(tmp_path / "records"), projected


def go(world, now, **options):
    settings, site, records, _ = world
    return run_predictions(settings, site, records=records, now=now, lock_when_due=True, **options)


def test_far_from_kickoff_the_week_is_projected_but_not_locked(world):
    summary = go(world, SUNDAY_KICKOFF_UTC - timedelta(hours=48))

    assert summary.predicted_week == 5
    assert summary.locked is False
    assert load_locked(world[2], 2026, 5) is None


def test_inside_the_window_the_week_is_locked(world):
    summary = go(world, SUNDAY_KICKOFF_UTC - timedelta(hours=6))

    assert summary.locked is True
    assert load_locked(world[2], 2026, 5) is not None


def test_after_kickoff_an_unlocked_week_is_refused_and_nothing_is_written(world):
    with pytest.raises(PredictionError, match="never locked"):
        go(world, SUNDAY_KICKOFF_UTC + timedelta(hours=1))

    assert load_locked(world[2], 2026, 5) is None
    assert world[1].list_keys("") == []


def test_a_run_too_close_to_kickoff_is_refused_too(world):
    with pytest.raises(PredictionError, match="never locked"):
        go(world, SUNDAY_KICKOFF_UTC - timedelta(minutes=10))

    assert load_locked(world[2], 2026, 5) is None


def test_an_unknowable_kickoff_refuses_rather_than_guessing(world, tmp_path):
    settings = world[0]
    connection = duckdb.connect(str(settings.warehouse_path))
    connection.execute("delete from stg_schedules")
    connection.close()

    with pytest.raises(PredictionError, match="no usable kickoff"):
        go(world, SUNDAY_KICKOFF_UTC - timedelta(hours=6))

    assert load_locked(world[2], 2026, 5) is None


def test_after_kickoff_a_week_that_was_locked_in_time_still_publishes_what_was_locked(world):
    go(world, SUNDAY_KICKOFF_UTC - timedelta(hours=6))
    world[3]["points"] = 99.0  # the model would now say something different

    summary = go(world, SUNDAY_KICKOFF_UTC + timedelta(hours=30))

    locked = load_locked(world[2], 2026, 5)
    assert locked.rows.points.tolist() == [10.0, 11.0]
    assert summary.locked is True
    assert world[3]["calls"] == 1, "a locked week must not be projected again"


def test_forcing_a_lock_still_works_for_a_person_running_it_by_hand(world):
    settings, site, records, _ = world

    summary = run_predictions(
        settings, site, records=records, now=SUNDAY_KICKOFF_UTC - timedelta(hours=72), lock=True
    )

    assert summary.locked is True


# ---------------------------------------------------------------- the daily command


@pytest.fixture
def daily(monkeypatch):
    calls = []
    outcome = {"pipeline": 0, "predict": 0}

    def fake_pipeline(_args, _settings, _now):
        calls.append("pipeline")
        return outcome["pipeline"]

    def fake_predict(args, _settings, _now):
        calls.append(("predict", args.lock, args.lock_when_due))
        return outcome["predict"]

    monkeypatch.setattr(cli, "_run_pipeline", fake_pipeline)
    monkeypatch.setattr(cli, "_run_predict", fake_predict)
    return calls, outcome


def test_daily_projects_after_a_good_run_and_asks_for_the_guarded_lock(daily):
    calls, _ = daily

    assert cli.main(["daily"]) == 0
    assert calls == ["pipeline", ("predict", False, True)]


def test_daily_makes_no_projection_from_a_run_that_failed(daily, capsys):
    calls, outcome = daily
    outcome["pipeline"] = 1

    assert cli.main(["daily"]) == 1
    assert calls == ["pipeline"]
    assert "no projections were made" in capsys.readouterr().err


def test_daily_fails_when_the_projection_step_fails(daily):
    _, outcome = daily
    outcome["predict"] = 1

    assert cli.main(["daily"]) == 1
