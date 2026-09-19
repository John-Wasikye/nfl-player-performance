"""Reading the feature store.

The store itself (dbt model `feat_player_week`) guarantees that a week's features never saw that
week's result. This module only selects and orders columns; it deliberately does no feature
engineering of its own, so there is exactly one place where leakage could be introduced and it is
covered by tests.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

# Grouped the way the research paper groups them, so an ablation can drop a whole group at once.
FEATURE_GROUPS: dict[str, list[str]] = {
    "form": [
        "ppr_mean3",
        "ppr_mean5",
        "ppr_mean10",
        "ppr_season_avg",
        "ppr_std8",
        "prior_games",
    ],
    "usage": [
        "attempts_mean5",
        "carries_mean5",
        "targets_mean5",
        "receptions_mean5",
        "target_share_mean5",
        "passing_yards_mean5",
        "rushing_yards_mean5",
        "receiving_yards_mean5",
        "snap_share_mean5",
        "pass_snaps_mean5",
        "target_per_pass_snap_mean5",
    ],
    "tracking": [
        "separation_mean8",
        "ryoe_mean8",
        "cpoe_mean8",
        "pressure_rate_mean8",
        "yac_contact_mean8",
    ],
    "game": [
        "implied_team_total",
        "team_spread",
        "total_line",
        "is_home",
        "rest_days",
        "is_divisional",
        "week",
    ],
    "weather": ["is_indoors", "wind", "temp"],
    "opponent": ["points_allowed_to_position_mean8"],
}

FEATURE_COLUMNS: list[str] = [c for group in FEATURE_GROUPS.values() for c in group]

# Kept alongside every row for grouping, grading and display, but never given to a model.
CONTEXT_COLUMNS = [
    "player_id",
    "season",
    "week",
    "position_group",
    "team",
    "opponent_team",
    "game_id",
    "injury_status",
    "is_questionable",
    "actual_ppr",
]

POSITIONS = ("QB", "RB", "WR", "TE", "K")


def load_features(warehouse: Path, seasons: tuple[int, int] | None = None) -> pd.DataFrame:
    """Every player-week from the feature store, oldest first.

    `position_code` is added because tree models need a number, not a label. Rows are returned for
    every player, including those who will be excluded later for being injured: deciding who plays
    is the availability model's job, not this one's.
    """
    where = ""
    if seasons is not None:
        where = f"where season between {seasons[0]} and {seasons[1]}"
    connection = duckdb.connect(str(warehouse), read_only=True)
    try:
        df = connection.sql(
            f"""
            select {", ".join(CONTEXT_COLUMNS + FEATURE_COLUMNS)}
            from feat_player_week
            {where}
            order by season, week, player_id
            """
        ).df()
    finally:
        connection.close()
    df["position_code"] = df.position_group.map({p: i for i, p in enumerate(POSITIONS)})
    for column in ("is_home", "is_divisional", "is_indoors", "is_questionable"):
        df[column] = df[column].astype("float64")
    return df


def model_columns() -> list[str]:
    """The columns a model is actually trained on."""
    return [*FEATURE_COLUMNS, "position_code"]
