"""When a week starts, and whether a forecast may still be locked for it.

A locked forecast is the project's evidence: it claims to have been written before kickoff.
Nothing else in the code knows what time it is, so this is the one place that refuses to call a
late forecast early. Every doubt here resolves to "do not lock".
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

# Lock only when the first game is this close, so a forecast is made with the latest injury reports
# rather than days before them.
LOCK_WINDOW = timedelta(hours=24)
# And refuse inside this margin, so a run that starts a minute before kickoff and takes five does
# not stamp a forecast as early when it finished late.
LOCK_MARGIN = timedelta(minutes=30)

# `kickoff_et` is a naive US-Eastern timestamp. Eastern is UTC-4 in summer and UTC-5 in winter; 4
# is used for both. In winter that places a game an hour earlier than it really starts, which can
# only make the guard refuse sooner. Zoneinfo would remove the hour but needs a timezone database
# that the slim container image does not have. This is deliberately the opposite direction to the
# freshness gate in publish.py: there an early estimate raises false alarms, here a late one would
# be dishonest.
EASTERN_TO_UTC_HOURS = 4


def _kickoff_utc(kickoff_et: datetime | None, game_date: date | None) -> datetime | None:
    if kickoff_et is not None:
        return kickoff_et.replace(tzinfo=timezone.utc) + timedelta(hours=EASTERN_TO_UTC_HOURS)
    if game_date is not None:
        # No time of day: assume the game could be at the very start of that date.
        return datetime(
            game_date.year, game_date.month, game_date.day, tzinfo=timezone.utc
        ) + timedelta(hours=EASTERN_TO_UTC_HOURS)
    return None


def first_kickoff_utc(warehouse: Path, season: int, week: int) -> datetime | None:
    """The week's earliest regular-season kickoff, or None if any game's start is unknowable."""
    connection = duckdb.connect(str(warehouse), read_only=True)
    try:
        games = connection.execute(
            "select kickoff_et, game_date from stg_schedules "
            "where season = ? and week = ? and game_type = 'REG'",
            [season, week],
        ).fetchall()
    finally:
        connection.close()
    if not games:
        return None
    starts = [_kickoff_utc(kickoff, day) for kickoff, day in games]
    if any(start is None for start in starts):
        return None
    return min(starts)


def lock_state(first_kickoff: datetime | None, now: datetime) -> str:
    """`wait` (too early), `lock` (due now), `missed` (too late) or `unknown` (cannot tell)."""
    if first_kickoff is None:
        return "unknown"
    reference = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
    until = first_kickoff - reference
    if until < LOCK_MARGIN:
        return "missed"
    if until <= LOCK_WINDOW:
        return "lock"
    return "wait"
