"""Season helpers."""

from __future__ import annotations

from datetime import date


def current_season(today: date) -> int:
    """Return the NFL season a calendar date belongs to.

    A season starts in September and ends with the Super Bowl in February, so
    January and February still belong to the season that began the previous
    year. From March on this returns the upcoming season, whose per-season
    files may not exist yet (the ingest treats that as "not available").
    """
    return today.year if today.month >= 3 else today.year - 1


def parse_seasons(spec: str) -> list[int]:
    """Parse "2025", "2024,2025" or "2021-2025" into a sorted list of seasons."""
    seasons: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid season range: {part}")
            seasons.update(range(start, end + 1))
        else:
            seasons.add(int(part))
    if not seasons:
        raise ValueError("no seasons given")
    return sorted(seasons)
