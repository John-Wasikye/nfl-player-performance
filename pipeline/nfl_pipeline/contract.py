"""The published data contract (version 1).

The website, and later the mobile app, read only these JSON files. Every file is built from the
models below and validated against them before it is written, so a schema change is always a
deliberate edit here (and a bump of SCHEMA_VERSION when it breaks readers).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

Position = Literal["QB", "RB", "WR", "TE", "K"]
POSITIONS: tuple[Position, ...] = ("QB", "RB", "WR", "TE", "K")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompositeView(Model):
    """Composite performance score: 70% efficiency and 30% production by default."""

    score: float | None = Field(ge=0, le=100)
    efficiency: float | None = Field(ge=0, le=100)
    production: float | None = Field(ge=0, le=100)
    rank: int | None = Field(ge=1)
    rank_prev: int | None = Field(ge=1)
    movement: int | None  # previous rank minus current rank: positive means moved up
    is_new: bool  # ranked for the first time after the season's first week


class FantasyView(Model):
    """Season-to-date PPR fantasy points (standard scoring for kickers)."""

    points: float
    per_game: float | None
    rank: int = Field(ge=1)
    rank_prev: int | None = Field(ge=1)
    movement: int | None
    is_new: bool


class RankedPlayer(Model):
    player_id: str
    name: str
    team: str
    injury_status: str | None
    games: int = Field(ge=0)
    qualified: bool  # False: listed but not ranked (too little volume for the week)
    composite: CompositeView
    fantasy: FantasyView


class RankingsFile(Model):
    """rankings/{season}/{week}/{position}.json. Ranked players first, then the unranked."""

    schema_version: int
    season: int
    week: int
    position: Position
    week_complete: bool
    players: list[RankedPlayer]


class BreakdownItem(Model):
    """One metric's share of a player's composite score."""

    metric: str
    component: Literal["efficiency", "production"]
    value: float
    percentile: float = Field(ge=0, le=1)
    weight: float
    contribution_points: float


class PlayerWeek(Model):
    week: int
    team: str
    games: int
    qualified: bool
    composite_rank: int | None
    composite_score: float | None
    efficiency_score: float | None
    production_score: float | None
    fantasy_rank: int
    ppr_points: float


class PlayerFile(Model):
    """players/{player_id}.json: a player's rank history this season and the latest breakdown."""

    schema_version: int
    player_id: str
    name: str
    position: Position
    team: str
    season: int
    latest_week: int
    history: list[PlayerWeek]
    breakdown: list[BreakdownItem]  # for the latest week; empty if the player is not ranked


class Mover(Model):
    player_id: str
    name: str
    team: str
    rank: int
    rank_prev: int
    movement: int


class MoversFile(Model):
    """movers/{season}/{week}.json: the biggest composite-rank risers and fallers per position."""

    schema_version: int
    season: int
    week: int
    risers: dict[Position, list[Mover]]
    fallers: dict[Position, list[Mover]]


class MetricWeight(Model):
    metric: str
    component: Literal["efficiency", "production"]
    direction: Literal["higher", "lower"]
    weight: float


class PositionMethodology(Model):
    position: Position
    min_role_per_week: float
    efficiency_weight: float
    production_weight: float
    metrics: list[MetricWeight]


class Methodology(Model):
    """methodology.json: the exact settings in use, so the site never drifts from the pipeline."""

    schema_version: int
    positions: list[PositionMethodology]
    kicker_scoring: str
    backtest: dict | None  # filled in once the backtest exists


class Meta(Model):
    """meta.json: written last, so it only ever points at a complete set of files."""

    schema_version: int
    generated_at: str
    pipeline_version: str
    data_as_of: dict[str, str]  # nflverse dataset -> when nflverse last updated it
    season: int
    latest_week: int
    week_complete: bool
    weeks: list[int]
    positions: list[Position]
