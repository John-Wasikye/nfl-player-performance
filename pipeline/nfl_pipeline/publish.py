"""Publish the rankings as versioned JSON files for the website (and, later, the app).

The publish step reads the dbt marts, builds every file in the contract (contract.py), and runs a
validation gate over them. Only if everything passes are the files written, and `meta.json` is
written last, so readers never see a half-published set. If the gate fails nothing is written and
the previously published data stays live.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb
from pydantic import ValidationError

from nfl_pipeline import __version__
from nfl_pipeline.backtest import summary_for_methodology
from nfl_pipeline.contract import (
    POSITIONS,
    SCHEMA_VERSION,
    BreakdownItem,
    CompositeView,
    FantasyView,
    Meta,
    Methodology,
    MetricWeight,
    Mover,
    MoversFile,
    PlayerFile,
    PlayerWeek,
    PositionMethodology,
    RankedPlayer,
    RankingsFile,
)
from nfl_pipeline.ingest import STATE_KEY
from nfl_pipeline.storage import Storage

logger = logging.getLogger("nfl_pipeline.publish")

DEFAULT_PREFIX = "published/v1"
BACKTEST_KEY = "backtest/summary.json"
MOVERS_PER_POSITION = 5

# The fewest ranked players we accept per position in the latest week. Far below a normal week;
# a value under this means the data is broken, not just quiet.
MIN_RANKED = {"QB": 8, "RB": 8, "WR": 8, "TE": 4, "K": 8}

# How long after kickoff we still accept "no result yet" in our own copy of the schedule.
# A game is over about 3.5 hours after kickoff and nflverse republishes within hours, so a
# game still unfinished in our data two days later means the ingest has stopped bringing in
# results. It does not mean the game ran long.
STALE_AFTER_HOURS = 48.0

# stg_schedules.kickoff_et is a naive US-Eastern timestamp. Converting it properly would mean
# depending on a timezone database (zoneinfo needs the tzdata package on Windows) to gain at
# most one hour of precision against a 48-hour threshold. Instead use the larger of the two
# Eastern offsets, which makes every game look up to an hour *more recent* than it really was.
# That can only ever delay a staleness complaint, never invent one.
EASTERN_TO_UTC_HOURS = 5

KICKER_SCORING = (
    "Field goals: 3 points under 40 yards, 4 for 40-49, 5 for 50+. Extra point: 1. "
    "Each missed field goal or extra point: -1."
)


class PublishError(Exception):
    """The data failed validation or could not be read; nothing was published."""


@dataclass
class PublishSummary:
    season: int
    latest_week: int
    files_written: int


def _num(value: Any) -> float | None:
    """A JSON-safe number: None for null, NaN, and infinity; rounded to keep files small."""
    if value is None:
        return None
    number = float(value)
    return round(number, 4) if math.isfinite(number) else None


def _rows(connection: duckdb.DuckDBPyConnection, sql: str, params: list | None = None):
    cursor = connection.execute(sql, params or [])
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def _json(model) -> bytes:
    return model.model_dump_json().encode("utf-8")


def _data_as_of(storage: Storage) -> dict[str, str]:
    """When nflverse last updated each dataset we ingested, from the ingest state file."""
    raw = storage.get_bytes(STATE_KEY)
    if not raw:
        return {}
    latest: dict[str, tuple[str, str]] = {}
    for file_id, entry in json.loads(raw).items():
        updated = entry.get("source_last_updated")
        ingested = entry.get("ingested_at", "")
        dataset = file_id.split("/", 1)[0]
        if updated and (dataset not in latest or ingested > latest[dataset][1]):
            latest[dataset] = (updated, ingested)
    return {dataset: value[0] for dataset, value in sorted(latest.items())}


def _ranked_player(row: dict) -> RankedPlayer:
    return RankedPlayer(
        player_id=row["player_id"],
        name=row["display_name"],
        team=row["team"],
        injury_status=row["injury_status"],
        games=row["games"],
        qualified=row["is_qualified"],
        composite=CompositeView(
            score=_num(row["composite_score"]),
            efficiency=_num(row["efficiency_score"]),
            production=_num(row["production_score"]),
            rank=row["composite_rank"],
            rank_prev=row["composite_rank_prev"],
            movement=row["composite_movement"],
            is_new=row["composite_is_new"],
        ),
        fantasy=FantasyView(
            points=_num(row["ppr_points"]) or 0.0,
            per_game=_num(row["ppr_per_game"]),
            rank=row["fantasy_rank"],
            rank_prev=row["fantasy_rank_prev"],
            movement=row["fantasy_movement"],
            is_new=row["fantasy_is_new"],
        ),
    )


def _sort_key(player: RankedPlayer) -> tuple:
    """Ranked players first (by composite rank), then unranked ones by fantasy rank."""
    if player.composite.rank is not None:
        return (0, player.composite.rank)
    return (1, player.fantasy.rank)


def _backtest_summary(storage: Storage) -> dict | None:
    """Headline backtest numbers for the methodology page, if a backtest has been run."""
    raw = storage.get_bytes(BACKTEST_KEY)
    if not raw:
        return None
    try:
        return summary_for_methodology(json.loads(raw))
    except (KeyError, TypeError, ValueError) as error:
        logger.warning("ignoring an unreadable backtest summary: %s", error)
        return None


def _methodology(connection: duckdb.DuckDBPyConnection, storage: Storage) -> Methodology:
    config = _rows(connection, "select * from ranking_config order by position_group")
    weights = _rows(connection, "select * from ranking_weights order by position_group, metric")
    positions = []
    for row in config:
        positions.append(
            PositionMethodology(
                position=row["position_group"],
                min_role_per_week=float(row["min_role_per_week"]),
                efficiency_weight=float(row["efficiency_weight"]),
                production_weight=float(row["production_weight"]),
                metrics=[
                    MetricWeight(
                        metric=w["metric"],
                        component=w["component"],
                        direction=w["direction"],
                        weight=float(w["weight"]),
                    )
                    for w in weights
                    if w["position_group"] == row["position_group"]
                ],
            )
        )
    order = {position: index for index, position in enumerate(POSITIONS)}
    positions.sort(key=lambda p: order[p.position])
    return Methodology(
        schema_version=SCHEMA_VERSION,
        positions=positions,
        kicker_scoring=KICKER_SCORING,
        backtest=_backtest_summary(storage),
    )


def _movers(week_rows: list[dict], season: int, week: int) -> MoversFile:
    risers: dict[str, list[Mover]] = {}
    fallers: dict[str, list[Mover]] = {}
    for position in POSITIONS:
        moved = [
            r
            for r in week_rows
            if r["position_group"] == position
            and r["composite_rank"] is not None
            and r["composite_movement"] is not None
        ]

        def mover(row: dict) -> Mover:
            return Mover(
                player_id=row["player_id"],
                name=row["display_name"],
                team=row["team"],
                rank=row["composite_rank"],
                rank_prev=row["composite_rank_prev"],
                movement=row["composite_movement"],
            )

        up = sorted(
            (r for r in moved if r["composite_movement"] > 0),
            key=lambda r: (-r["composite_movement"], r["composite_rank"]),
        )
        down = sorted(
            (r for r in moved if r["composite_movement"] < 0),
            key=lambda r: (r["composite_movement"], r["composite_rank"]),
        )
        risers[position] = [mover(r) for r in up[:MOVERS_PER_POSITION]]
        fallers[position] = [mover(r) for r in down[:MOVERS_PER_POSITION]]
    return MoversFile(
        schema_version=SCHEMA_VERSION, season=season, week=week, risers=risers, fallers=fallers
    )


def _kickoff_utc(kickoff_et: datetime | None, game_date: date | None) -> datetime | None:
    """When a game started, in UTC, erring on the side of "more recently than that".

    Falls back to the game date when the parsed kickoff is missing, so a game with an
    unreadable time is still checked rather than quietly skipped. End of day is used for that
    fallback for the same reason as the fixed offset above: it can only make the game look
    more recent, so it never manufactures a staleness complaint.
    """
    if kickoff_et is not None:
        return kickoff_et.replace(tzinfo=timezone.utc) + timedelta(hours=EASTERN_TO_UTC_HOURS)
    if game_date is not None:
        return datetime(
            game_date.year, game_date.month, game_date.day, 23, 59, tzinfo=timezone.utc
        ) + timedelta(hours=EASTERN_TO_UTC_HOURS)
    return None


def _freshness_problems(
    connection: duckdb.DuckDBPyConnection,
    *,
    season: int,
    latest_ranked_week: int,
    now: datetime,
    stale_after_hours: float = STALE_AFTER_HOURS,
) -> list[str]:
    """Refuse to republish yesterday's numbers as though they were today's.

    The ingest skips any file whose source has not changed, which is what keeps the daily run
    cheap. The failure mode is that a stalled or broken source looks exactly like a quiet week:
    every step reports success, the gate sees a complete and internally consistent set of
    files, and last week's rankings go out as current. Nothing errors.

    Two independent checks, because the two break differently and either can happen alone:

    A. **Our copy of reality is behind reality.** A regular-season game kicked off long enough
       ago that it must be over, and our schedule still records no result for it.
    B. **The rankings are behind our copy.** A week has had a settled result for long enough
       that it should have been ranked, and the rankings do not reach it. That points at dbt or
       the publish lagging the raw data rather than at the ingest.

    The same threshold drives both, which also absorbs the ordinary case of nflverse publishing
    a schedule result before the weekly player stats that go with it.
    """
    reference = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    cutoff = reference - timedelta(hours=stale_after_hours)
    try:
        games = _rows(
            connection,
            """
            select week, is_final, kickoff_et, game_date
            from stg_schedules
            where season = ? and game_type = 'REG'
            """,
            [season],
        )
    except duckdb.Error as error:
        # A check that cannot run must not pass quietly.
        return [f"could not read stg_schedules to check data freshness: {error}"]
    if not games:
        return [f"stg_schedules has no regular-season games for season {season}"]

    started = {id(g): _kickoff_utc(g["kickoff_et"], g["game_date"]) for g in games}
    undated = [g for g in games if started[id(g)] is None]
    overdue = [
        g
        for g in games
        if not g["is_final"] and started[id(g)] is not None and started[id(g)] < cutoff
    ]
    settled = [
        g for g in games if g["is_final"] and started[id(g)] is not None and started[id(g)] < cutoff
    ]

    problems: list[str] = []
    if undated:
        problems.append(
            f"{len(undated)} regular-season game(s) in season {season} have neither a kickoff "
            "time nor a date, so their freshness cannot be checked"
        )
    if overdue:
        earliest = min(overdue, key=lambda g: (g["week"], str(g["game_date"])))
        problems.append(
            f"{len(overdue)} regular-season game(s) kicked off more than {stale_after_hours:g}h "
            f"ago and still have no result in stg_schedules (earliest: week {earliest['week']}, "
            f"{earliest['game_date']}). The raw data has stopped updating, so publishing now "
            "would serve stale rankings as current."
        )
    if settled:
        newest_settled_week = max(g["week"] for g in settled)
        if latest_ranked_week < newest_settled_week:
            problems.append(
                f"week {newest_settled_week} has had a final result for more than "
                f"{stale_after_hours:g}h but the rankings stop at week {latest_ranked_week}; "
                "the rankings are behind the raw data"
            )
    return problems


def _check_rankings(file: RankingsFile) -> list[str]:
    """Validation gate for one rankings file. Returns a list of problems (empty means OK)."""
    where = f"rankings {file.season} week {file.week} {file.position}"
    problems: list[str] = []
    players = file.players
    if not players:
        return [f"{where}: no players"]
    ids = [p.player_id for p in players]
    if len(ids) != len(set(ids)):
        problems.append(f"{where}: duplicate player ids")
    ranked = [p.composite.rank for p in players if p.composite.rank is not None]
    if sorted(ranked) != list(range(1, len(ranked) + 1)):
        problems.append(f"{where}: composite ranks are not 1..{len(ranked)} without gaps")
    fantasy = sorted(p.fantasy.rank for p in players)
    if fantasy != list(range(1, len(players) + 1)):
        problems.append(f"{where}: fantasy ranks are not 1..{len(players)} without gaps")
    if [_sort_key(p) for p in players] != sorted(_sort_key(p) for p in players):
        problems.append(f"{where}: players are not in display order")
    for p in players:
        if p.qualified != (p.composite.rank is not None):
            problems.append(f"{where}: {p.player_id} qualified flag disagrees with its rank")
        if not p.qualified and p.composite.score is not None:
            problems.append(f"{where}: {p.player_id} is unranked but has a score")
    return problems


def build_files(
    connection: duckdb.DuckDBPyConnection, storage: Storage, *, season: int, now: datetime
) -> tuple[dict[str, bytes], PublishSummary]:
    """Build every published file in memory and validate it. Raises PublishError on any problem."""
    try:
        weeks = [
            r["week"]
            for r in _rows(
                connection,
                "select distinct week from mart_rankings where season = ? order by week",
                [season],
            )
        ]
    except duckdb.Error as error:
        raise PublishError(f"could not read the rankings tables: {error}") from error
    if not weeks:
        raise PublishError(f"no rankings found for season {season}")
    latest_week = weeks[-1]

    rows = _rows(
        connection,
        """
        select week, position_group, player_id, display_name, team, injury_status, games,
               is_qualified, week_complete, composite_score, efficiency_score, production_score,
               composite_rank, composite_rank_prev, composite_movement, composite_is_new,
               ppr_points, ppr_per_game, fantasy_rank, fantasy_rank_prev, fantasy_movement,
               fantasy_is_new
        from mart_rankings
        where season = ?
        """,
        [season],
    )
    by_week_position: dict[tuple[int, str], list[dict]] = {}
    for row in rows:
        by_week_position.setdefault((row["week"], row["position_group"]), []).append(row)

    files: dict[str, bytes] = {}
    problems: list[str] = []
    prefix = DEFAULT_PREFIX

    for week in weeks:
        complete = all(
            r["week_complete"]
            for position in POSITIONS
            for r in by_week_position.get((week, position), [])
        )
        for position in POSITIONS:
            group = by_week_position.get((week, position), [])
            players = sorted((_ranked_player(r) for r in group), key=_sort_key)
            ranking = RankingsFile(
                schema_version=SCHEMA_VERSION,
                season=season,
                week=week,
                position=position,
                week_complete=complete,
                players=players,
            )
            problems.extend(_check_rankings(ranking))
            if week == latest_week:
                ranked_count = sum(1 for p in players if p.composite.rank is not None)
                if ranked_count < MIN_RANKED[position]:
                    problems.append(
                        f"{position} week {week}: only {ranked_count} ranked players "
                        f"(expected at least {MIN_RANKED[position]})"
                    )
            files[f"{prefix}/rankings/{season}/{week}/{position}.json"] = _json(ranking)

    latest_rows = [r for r in rows if r["week"] == latest_week]
    files[f"{prefix}/movers/{season}/{latest_week}.json"] = _json(
        _movers(latest_rows, season, latest_week)
    )

    breakdown_by_player: dict[str, list[BreakdownItem]] = {}
    for b in _rows(
        connection,
        """
        select player_id, metric, component, metric_value, percentile, weight, contribution_points
        from mart_ranking_breakdown
        where season = ? and week = ?
        order by player_id, contribution_points desc
        """,
        [season, latest_week],
    ):
        breakdown_by_player.setdefault(b["player_id"], []).append(
            BreakdownItem(
                metric=b["metric"],
                component=b["component"],
                value=_num(b["metric_value"]),
                percentile=_num(b["percentile"]),
                weight=_num(b["weight"]),
                contribution_points=_num(b["contribution_points"]),
            )
        )

    history: dict[str, list[dict]] = {}
    for row in sorted(rows, key=lambda r: (r["player_id"], r["week"])):
        history.setdefault(row["player_id"], []).append(row)
    for player_id, player_rows in history.items():
        last = player_rows[-1]
        files[f"{prefix}/players/{player_id}.json"] = _json(
            PlayerFile(
                schema_version=SCHEMA_VERSION,
                player_id=player_id,
                name=last["display_name"],
                position=last["position_group"],
                team=last["team"],
                season=season,
                latest_week=last["week"],
                history=[
                    PlayerWeek(
                        week=r["week"],
                        team=r["team"],
                        games=r["games"],
                        qualified=r["is_qualified"],
                        composite_rank=r["composite_rank"],
                        composite_score=_num(r["composite_score"]),
                        efficiency_score=_num(r["efficiency_score"]),
                        production_score=_num(r["production_score"]),
                        fantasy_rank=r["fantasy_rank"],
                        ppr_points=_num(r["ppr_points"]) or 0.0,
                    )
                    for r in player_rows
                ],
                breakdown=breakdown_by_player.get(player_id, [])
                if last["week"] == latest_week
                else [],
            )
        )

    try:
        files[f"{prefix}/methodology.json"] = _json(_methodology(connection, storage))
    except duckdb.Error as error:
        problems.append(f"could not read the ranking settings: {error}")

    problems.extend(
        _freshness_problems(connection, season=season, latest_ranked_week=latest_week, now=now)
    )

    if problems:
        raise PublishError(
            f"validation failed with {len(problems)} problem(s); nothing was published:\n  "
            + "\n  ".join(problems[:20])
        )

    week_complete = all(r["week_complete"] for r in latest_rows)
    meta = Meta(
        schema_version=SCHEMA_VERSION,
        generated_at=now.isoformat(),
        pipeline_version=__version__,
        data_as_of=_data_as_of(storage),
        season=season,
        latest_week=latest_week,
        week_complete=week_complete,
        weeks=weeks,
        positions=list(POSITIONS),
    )
    files[f"{prefix}/meta.json"] = _json(meta)
    return files, PublishSummary(season=season, latest_week=latest_week, files_written=len(files))


def publish(
    warehouse_path: Path,
    storage: Storage,
    *,
    now: datetime,
    season: int | None = None,
) -> PublishSummary:
    """Validate and publish. `meta.json` is written last, after every other file."""
    if not Path(warehouse_path).exists():
        raise PublishError(f"warehouse not found: {warehouse_path} (run the dbt build first)")
    connection = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        if season is None:
            try:
                (season,) = connection.execute("select max(season) from mart_rankings").fetchone()
            except duckdb.Error as error:
                raise PublishError(f"could not read the rankings tables: {error}") from error
            if season is None:
                raise PublishError("mart_rankings is empty")
        try:
            files, summary = build_files(connection, storage, season=season, now=now)
        except ValidationError as error:
            raise PublishError(
                f"a file did not match the contract; nothing published: {error}"
            ) from error
    finally:
        connection.close()

    meta_key = f"{DEFAULT_PREFIX}/meta.json"
    for key in sorted(key for key in files if key != meta_key):
        storage.put_bytes(key, files[key])
    storage.put_bytes(meta_key, files[meta_key])
    logger.info(
        "published season %s through week %s (%s files)",
        summary.season,
        summary.latest_week,
        summary.files_written,
    )
    return summary
