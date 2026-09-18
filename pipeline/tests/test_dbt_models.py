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


def run_dbt(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "RAW_ROOT": str(tmp_path / "raw"),
        "WAREHOUSE_PATH": str(tmp_path / "warehouse.duckdb"),
        "DBT_TARGET_PATH": str(tmp_path / "target"),
        "DBT_LOG_PATH": str(tmp_path / "logs"),
    }
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
