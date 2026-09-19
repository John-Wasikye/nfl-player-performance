"""Integration tests: run the real dbt project against a tiny fixture raw lake.

These check that the models clean data correctly (latest snapshot wins, legacy team codes are
standardized, headshot URLs are dropped) and that the data quality tests actually fail on bad data.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO = Path(__file__).resolve().parents[2]
DBT_DIR = REPO / "dbt"

pytestmark = pytest.mark.skipif(
    not (DBT_DIR / "dbt_project.yml").exists(), reason="dbt project not found"
)


def write_parquet(root: Path, dataset: str, rows: list[dict], *, season=None, ingest="2026-09-18"):
    """Write rows to raw/<dataset>/[season=<year>/]ingest_date=<date>/<dataset>.parquet."""
    folder = root / dataset
    if season is not None:
        folder = folder / f"season={season}"
    folder = folder / f"ingest_date={ingest}"
    folder.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), folder / f"{dataset}.parquet")


def stat_line(player_id, name, position, team, **overrides):
    line = {
        "player_id": player_id,
        "player_name": name,
        "player_display_name": name,
        "position": position,
        "position_group": position,
        "headshot_url": "https://static.www.nfl.com/image/upload/x",
        "season": 2026,
        "season_type": "REG",
        "week": 1,
        "team": team,
        "opponent_team": "KC",
        "fg_made_list": None,
        "fg_missed_list": None,
        "fg_blocked_list": None,
        "gwfg_distance": None,
        "attempts": 0,
        "completions": 0,
        "passing_yards": 0,
        "carries": 0,
        "targets": 0,
        "receptions": 0,
        "fg_att": 0,
        "fg_made": 0,
        "pat_att": 0,
        "pat_made": 0,
        "fantasy_points": 0.0,
        "fantasy_points_ppr": 0.0,
        # columns the ranking models read
        "passing_tds": 0,
        "passing_interceptions": 0,
        "sacks_suffered": 0,
        "passing_epa": 0.0,
        "passing_cpoe": 0.0,
        "rushing_yards": 0,
        "rushing_tds": 0,
        "rushing_epa": 0.0,
        "rushing_first_downs": 0,
        "receiving_yards": 0,
        "receiving_tds": 0,
        "receiving_epa": 0.0,
        "receiving_air_yards": 0,
        "receiving_first_downs": 0,
        "target_share": 0.0,
        "air_yards_share": 0.0,
        "wopr": 0.0,
        "fg_made_0_19": 0,
        "fg_made_20_29": 0,
        "fg_made_30_39": 0,
        "fg_made_40_49": 0,
        "fg_made_50_59": 0,
        "fg_made_60_": 0,
        "fg_missed": 0,
        "fg_missed_40_49": 0,
        "fg_missed_50_59": 0,
        "fg_missed_60_": 0,
        "pat_missed": 0,
    }
    line.update(overrides)
    return line


def build_raw_lake(root: Path, *, stats: list[dict] | None = None) -> None:
    write_parquet(
        root,
        "schedules",
        [
            {
                "game_id": "2026_01_OAK_KC",
                "season": 2026,
                "game_type": "REG",
                "week": 1,
                "gameday": "2026-09-13",
                "weekday": "Sunday",
                "gametime": "13:00",
                "home_team": "KC",
                "away_team": "OAK",  # legacy code: should become LV
                "home_score": 27,
                "away_score": 20,
                "overtime": 0,
                "location": "Home",
                "home_rest": 7,
                "away_rest": 7,
                "spread_line": -3.5,
                "total_line": 47.5,
                "home_moneyline": -180,
                "away_moneyline": 150,
                "div_game": 1,
                "roof": "outdoors",
                "surface": "grass",
                "temp": 70,
                "wind": 5,
                "stadium_id": "KAN00",
                "stadium": "Arrowhead",
                "home_qb_id": "P1",
                "away_qb_id": "P4",
                "home_coach": "A",
                "away_coach": "B",
            }
        ],
    )
    players = [
        ("P1", "Pat Passer", "QB", "KC", "PFR1"),
        ("P2", "Will Receiver", "WR", "OAK", "PFR2"),
        ("P3", "Kim Kicker", "K", "KC", "PFR3"),
    ]
    write_parquet(
        root,
        "players",
        [
            {
                "gsis_id": gsis,
                "display_name": name,
                "first_name": name.split()[0],
                "last_name": name.split()[1],
                "birth_date": "1995-01-01",
                "position": position,
                "height": 75,
                "weight": 210,
                "college_name": "State",
                "rookie_season": 2018,
                "last_season": 2026,
                "latest_team": team,
                "status": "ACT",
                "years_of_experience": 8,
                "draft_year": 2018,
                "draft_round": 1,
                "draft_pick": 5,
                "pfr_id": pfr,
                "espn_id": "1",
            }
            for gsis, name, position, team, pfr in players
        ],
    )
    write_parquet(
        root,
        "stats_player",
        stats
        or [
            stat_line(
                "P1",
                "P.Passer",
                "QB",
                "KC",
                attempts=30,
                completions=20,
                passing_yards=300,
                fantasy_points=20.0,
                fantasy_points_ppr=20.0,
            ),
            stat_line(
                "P2",
                "W.Receiver",
                "WR",
                "OAK",
                targets=8,
                receptions=6,
                fantasy_points=9.0,
                fantasy_points_ppr=15.0,
            ),
            stat_line(
                "P3",
                "K.Kicker",
                "K",
                "KC",
                fg_att=2,
                fg_made=2,
                pat_att=3,
                pat_made=3,
                fantasy_points=9.0,
                fantasy_points_ppr=9.0,
            ),
            stat_line(None, "Unattributed", "QB", "KC"),  # no player id: must be dropped
        ],
        season=2026,
    )
    # An older snapshot with different numbers: the newer snapshot above must win.
    write_parquet(
        root,
        "stats_player",
        [stat_line("P1", "P.Passer", "QB", "KC", attempts=1, completions=1, passing_yards=1)],
        season=2026,
        ingest="2026-09-10",
    )
    write_parquet(
        root,
        "snap_counts",
        [
            {
                "game_id": "2026_01_OAK_KC",
                "season": 2026,
                "week": 1,
                "game_type": "REG",
                "pfr_player_id": "PFR2",
                "player": "Will Receiver",
                "position": "WR",
                "team": "OAK",
                "offense_snaps": 60.0,
                "offense_pct": 0.9,
                "defense_snaps": 0.0,
                "defense_pct": 0.0,
                "st_snaps": 5.0,
                "st_pct": 0.2,
            }
        ],
    )
    write_parquet(
        root,
        "injuries",
        [
            {
                "gsis_id": "P2",
                "season": 2026,
                "week": 1,
                "team": "OAK",
                "report_status": "Questionable",
                "report_primary_injury": "Ankle",
                "practice_status": "Limited",
            }
        ],
    )


# The fixture lake below carries the core datasets only, so the models that read play-by-play,
# participation, advanced stats or charting are excluded here. Those are covered by the real
# `dbt build` against the full lake; these tests are about the cleaning and ranking logic.
FIXTURELESS = "stg_pbp_plays+ stg_participation+ stg_advstats+ stg_ftn_charting+"


def run_dbt(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "RAW_ROOT": str(tmp_path / "raw"),
        "WAREHOUSE_PATH": str(tmp_path / "warehouse.duckdb"),
        "DBT_TARGET_PATH": str(tmp_path / "target"),
        "DBT_LOG_PATH": str(tmp_path / "logs"),
    }
    if args and args[0] in {"build", "run"}:
        args = (*args, "--exclude", FIXTURELESS)
    command = [
        sys.executable,
        "-c",
        "import sys; from dbt.cli.main import cli; sys.exit(cli())",
        *args,
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
    ]
    return subprocess.run(command, env=env, capture_output=True, text=True, cwd=tmp_path)


def query(tmp_path: Path, sql: str):
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True)
    try:
        return con.sql(sql).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def built_lake(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("good_lake")
    build_raw_lake(tmp_path / "raw")
    result = run_dbt(tmp_path, "build")
    return tmp_path, result


def test_dbt_build_passes_on_clean_data(built_lake):
    _, result = built_lake

    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def test_newest_snapshot_wins(built_lake):
    tmp_path, _ = built_lake

    rows = query(tmp_path, "select passing_yards from fct_player_week where player_id = 'P1'")

    assert rows == [(300,)]  # not the stale 1 from the 2026-09-10 snapshot


def test_rows_without_a_player_id_are_dropped(built_lake):
    tmp_path, _ = built_lake

    assert query(tmp_path, "select count(*) from fct_player_week") == [(3,)]


def test_legacy_team_codes_are_standardized(built_lake):
    tmp_path, _ = built_lake

    assert query(tmp_path, "select away_team from dim_game") == [("LV",)]
    assert query(tmp_path, "select team from fct_player_week where player_id = 'P2'") == [("LV",)]


def test_headshot_urls_never_reach_the_warehouse(built_lake):
    tmp_path, _ = built_lake

    columns = {row[0] for row in query(tmp_path, "describe fct_player_week")}
    assert "headshot_url" not in columns


def test_snap_counts_and_injuries_attach_to_the_player_week(built_lake):
    tmp_path, _ = built_lake

    rows = query(
        tmp_path,
        "select offense_pct, injury_status from fct_player_week where player_id = 'P2'",
    )

    assert rows == [(0.9, "Questionable")]


def test_stat_lines_are_linked_to_their_game(built_lake):
    tmp_path, _ = built_lake

    rows = query(tmp_path, "select distinct game_id from fct_player_week")

    assert rows == [("2026_01_OAK_KC",)]


def test_an_unmapped_position_fails_the_data_quality_tests(tmp_path):
    bad = [stat_line("P1", "P.Passer", "XYZ", "KC")]
    build_raw_lake(tmp_path / "raw", stats=bad)

    result = run_dbt(tmp_path, "build")

    assert result.returncode != 0
    assert "position_group" in result.stdout


def test_impossible_stats_fail_the_data_quality_tests(tmp_path):
    bad = [stat_line("P1", "P.Passer", "QB", "KC", attempts=10, completions=25)]
    build_raw_lake(tmp_path / "raw", stats=bad)

    result = run_dbt(tmp_path, "build")

    assert result.returncode != 0
    assert "attempts >= completions" in result.stdout.replace("_", " ") or (
        "expression_is_true_fct_player_week" in result.stdout
    )


# --- Rankings -----------------------------------------------------------------------------------


def build_ranking_lake(root: Path, week2_epa: dict[str, float]) -> None:
    """Three quarterbacks over two weeks. Week 1 EPA is fixed; week 2 EPA is a parameter."""
    week1_epa = {"Q1": 10.0, "Q2": 5.0, "Q3": 0.0}
    names = {"Q1": "Quinn One", "Q2": "Quinn Two", "Q3": "Quinn Three", "Q4": "Quinn Four"}
    games = []
    for week, gameday in ((1, "2026-09-13"), (2, "2026-09-20")):
        games.append(
            {
                "game_id": f"2026_0{week}_AAA_BBB",
                "season": 2026,
                "game_type": "REG",
                "week": week,
                "gameday": gameday,
                "weekday": "Sunday",
                "gametime": "13:00",
                "home_team": "KC",
                "away_team": "LV",
                "home_score": 24,
                "away_score": 17,
                "overtime": 0,
                "location": "Home",
                "home_rest": 7,
                "away_rest": 7,
                "spread_line": -3.0,
                "total_line": 45.0,
                "home_moneyline": -150,
                "away_moneyline": 130,
                "div_game": 0,
                "roof": "outdoors",
                "surface": "grass",
                "temp": 70,
                "wind": 5,
                "stadium_id": "KAN00",
                "stadium": "Arrowhead",
                "home_qb_id": "Q1",
                "away_qb_id": "Q2",
                "home_coach": "A",
                "away_coach": "B",
            }
        )
    write_parquet(root, "schedules", games)
    write_parquet(
        root,
        "players",
        [
            {
                "gsis_id": pid,
                "display_name": name,
                "first_name": name.split()[0],
                "last_name": name.split()[1],
                "birth_date": "1995-01-01",
                "position": "QB",
                "height": 75,
                "weight": 210,
                "college_name": "State",
                "rookie_season": 2018,
                "last_season": 2026,
                "latest_team": "KC",
                "status": "ACT",
                "years_of_experience": 8,
                "draft_year": 2018,
                "draft_round": 1,
                "draft_pick": 5,
                "pfr_id": f"PFR{pid}",
                "espn_id": "1",
            }
            for pid, name in names.items()
        ],
    )
    lines = []
    for week, epa_by_player in ((1, week1_epa), (2, week2_epa)):
        for pid, epa in epa_by_player.items():
            lines.append(
                stat_line(
                    pid,
                    names[pid],
                    "QB",
                    "KC",
                    week=week,
                    attempts=30,
                    completions=20,
                    passing_yards=250,
                    passing_epa=epa,
                )
            )
    # A backup with 5 attempts a week: below the 14-per-week minimum, so listed but never ranked.
    for week in (1, 2):
        lines.append(
            stat_line(
                "Q4",
                names["Q4"],
                "QB",
                "KC",
                week=week,
                attempts=5,
                completions=3,
                passing_yards=30,
                passing_epa=50.0,
            )
        )
    write_parquet(root, "stats_player", lines, season=2026)
    write_parquet(
        root,
        "snap_counts",
        [
            {
                "game_id": "2026_01_AAA_BBB",
                "season": 2026,
                "week": 1,
                "game_type": "REG",
                "pfr_player_id": "PFRQ1",
                "player": "Quinn One",
                "position": "QB",
                "team": "KC",
                "offense_snaps": 60.0,
                "offense_pct": 1.0,
                "defense_snaps": 0.0,
                "defense_pct": 0.0,
                "st_snaps": 0.0,
                "st_pct": 0.0,
            }
        ],
    )
    write_parquet(
        root,
        "injuries",
        [
            {
                "gsis_id": "Q1",
                "season": 2026,
                "week": 1,
                "team": "KC",
                "report_status": "Questionable",
                "report_primary_injury": "Knee",
                "practice_status": "Limited",
            }
        ],
    )


def build_rankings(tmp_path: Path, week2_epa: dict[str, float]) -> None:
    build_ranking_lake(tmp_path / "raw", week2_epa)
    for args in (["seed"], ["run", "--select", "+mart_rankings"]):
        result = run_dbt(tmp_path, *args)
        assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]


def ranks(tmp_path: Path, week: int) -> dict[str, int]:
    rows = query(
        tmp_path,
        "select player_id, composite_rank from mart_rankings "
        f"where week = {week} and composite_rank is not null",
    )
    return dict(rows)


def test_rankings_never_use_future_weeks(tmp_path_factory):
    """Changing week 2 results must not change any week 1 rank or score (no lookahead)."""
    good = tmp_path_factory.mktemp("week2_a")
    build_rankings(good, {"Q1": 10.0, "Q2": 5.0, "Q3": 0.0})
    bad = tmp_path_factory.mktemp("week2_b")
    build_rankings(bad, {"Q1": -50.0, "Q2": 40.0, "Q3": 99.0})

    scores_sql = "select player_id, composite_score from mart_rankings where week = 1 order by 1"
    assert query(good, scores_sql) == query(bad, scores_sql)
    assert ranks(good, 1) == ranks(bad, 1) == {"Q1": 1, "Q2": 2, "Q3": 3}
    # ...while week 2 does respond to the new results
    assert ranks(good, 2) != ranks(bad, 2)


def test_rank_movement_is_previous_rank_minus_current_rank(tmp_path):
    build_rankings(tmp_path, {"Q1": -20.0, "Q2": 10.0, "Q3": 6.0})

    assert ranks(tmp_path, 1) == {"Q1": 1, "Q2": 2, "Q3": 3}
    assert ranks(tmp_path, 2) == {"Q2": 1, "Q3": 2, "Q1": 3}
    movement = dict(
        query(
            tmp_path,
            "select player_id, composite_movement from mart_rankings "
            "where week = 2 and composite_rank is not null",
        )
    )
    assert movement == {"Q2": 1, "Q3": 1, "Q1": -2}  # positive means moved up
    first_week = query(
        tmp_path, "select count(composite_movement) from mart_rankings where week = 1"
    )
    assert first_week == [(0,)]  # nothing to compare against in the first week


def test_a_low_volume_player_is_listed_but_not_ranked(tmp_path):
    build_rankings(tmp_path, {"Q1": 10.0, "Q2": 5.0, "Q3": 0.0})

    rows = query(
        tmp_path,
        "select is_qualified, composite_rank, composite_score, fantasy_rank "
        "from mart_rankings where week = 2 and player_id = 'Q4'",
    )

    # Q4 has a huge EPA total but only 10 attempts: listed, scored by nothing, and not ranked.
    assert rows == [(False, None, None, 4)]
    assert ranks(tmp_path, 2).keys() == {"Q1", "Q2", "Q3"}


def test_a_team_that_has_not_played_this_week_is_not_penalized(tmp_path):
    """Regression: the minimum role scales with games the team has played, not the week number.

    In a week that is still in progress, a quarterback whose team has not played yet has one game
    behind him. He must be held to a one-game standard, not the week number's two-game standard.
    """
    root = tmp_path / "raw"
    build_ranking_lake(root, {"Q1": 10.0, "Q2": 5.0, "Q3": 0.0})

    def game(game_id, week, home, away, final):
        return {
            "game_id": game_id, "season": 2026, "game_type": "REG", "week": week,
            "gameday": "2026-09-20", "weekday": "Sunday", "gametime": "13:00",
            "home_team": home, "away_team": away,
            "home_score": 24 if final else None, "away_score": 17 if final else None,
            "overtime": 0, "location": "Home", "home_rest": 7, "away_rest": 7,
            "spread_line": -3.0, "total_line": 45.0, "home_moneyline": -150,
            "away_moneyline": 130, "div_game": 0, "roof": "outdoors", "surface": "grass",
            "temp": 70, "wind": 5, "stadium_id": "X", "stadium": "X", "home_qb_id": "Q1",
            "away_qb_id": "Q2", "home_coach": "A", "away_coach": "B",
        }  # fmt: skip

    write_parquet(
        root,
        "schedules",
        [
            game("g1", 1, "KC", "LV", final=True),
            game("g2", 2, "KC", "DEN", final=True),
            game("g3", 2, "LV", "SF", final=False),  # Las Vegas has not played week 2 yet
        ],
    )
    # Q5 plays for Las Vegas: 20 attempts in week 1 and nothing yet in week 2.
    folder = root / "stats_player" / "season=2026" / "ingest_date=2026-09-18"
    pq.write_table(
        pa.Table.from_pylist(
            [stat_line("Q5", "Quinn Five", "QB", "LV", week=1, attempts=20, completions=12)]
        ),
        folder / "extra.parquet",
    )
    for args in (["seed"], ["run", "--select", "+mart_rankings"]):
        result = run_dbt(tmp_path, *args)
        assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]

    rows = query(
        tmp_path,
        "select is_qualified, composite_rank is not null from mart_rankings "
        "where week = 2 and player_id = 'Q5'",
    )
    # 20 attempts against a one-game minimum of 14: qualified. (Two games would need 28.)
    assert rows == [(True, True)]
