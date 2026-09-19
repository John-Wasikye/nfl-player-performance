"""Shared loading helpers for the prediction research analyses.

Everything reads the local warehouse and raw play-by-play, so results are reproducible with:
    .venv\\Scripts\\python research\\<analysis>.py
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
PBP_GLOB = (ROOT / "data" / "raw" / "pbp" / "season=*" / "ingest_date=*" / "*.parquet").as_posix()
SEASONS = (2021, 2025)
RESULTS = ROOT / "research" / "results"


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(WAREHOUSE), read_only=True)


def schedule(con) -> pd.DataFrame:
    """Final regular-season games, 2021-2025, with lines, weather, roof and stadium."""
    return con.sql(
        f"""
        select game_id, season, week, home_team, away_team, home_score, away_score, location,
               roof, temp, wind, spread_line, total_line, home_rest, away_rest, stadium_id,
               is_divisional, kickoff_et
        from stg_schedules
        where game_type = 'REG' and is_final and season between {SEASONS[0]} and {SEASONS[1]}
        """
    ).df()


def pbp(con) -> pd.DataFrame:
    """Regular-season plays 2021-2025 with the columns the analyses use."""
    return con.sql(
        f"""
        select game_id, season, week, posteam, defteam, home_team, away_team, posteam_type,
               play_type, penalty, penalty_team, penalty_type, epa, yardline_100,
               rush_attempt, pass_attempt, touchdown, td_team, rusher_player_id,
               receiver_player_id, passer_player_id, sack, qb_dropback, yards_gained,
               complete_pass, air_yards, field_goal_result, kick_distance, td_player_id,
               rush_touchdown, pass_touchdown, down, ydstogo, score_differential
        from read_parquet('{PBP_GLOB}', hive_partitioning = false, union_by_name = true)
        where season_type = 'REG' and season between {SEASONS[0]} and {SEASONS[1]}
        """
    ).df()


def save(name: str, payload: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{name}.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8"
    )


def se(values) -> float:
    """Standard error of the mean."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float(arr.std(ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else float("nan")
