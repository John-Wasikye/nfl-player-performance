"""The nflverse datasets the pipeline ingests.

nflverse publishes each dataset as files attached to a GitHub release. A
release also carries a `timestamp.json` that says when its data last changed,
which lets the ingest skip datasets that have not changed since the last run.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"


@dataclass(frozen=True)
class SourceFile:
    """One downloadable file from an nflverse release."""

    dataset: str
    release_tag: str
    filename: str
    season: int | None

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.release_tag}/{self.filename}"

    @property
    def timestamp_url(self) -> str:
        return f"{BASE_URL}/{self.release_tag}/timestamp.json"

    @property
    def file_id(self) -> str:
        return f"{self.dataset}/{self.filename}"


@dataclass(frozen=True)
class Dataset:
    name: str
    release_tag: str
    filename: str  # contains "{season}" for per-season datasets
    per_season: bool

    def files(self, seasons: Iterable[int]) -> list[SourceFile]:
        if not self.per_season:
            return [SourceFile(self.name, self.release_tag, self.filename, None)]
        return [
            SourceFile(self.name, self.release_tag, self.filename.format(season=season), season)
            for season in seasons
        ]


DATASETS: dict[str, Dataset] = {
    dataset.name: dataset
    for dataset in (
        Dataset("schedules", "schedules", "games.parquet", per_season=False),
        Dataset("players", "players", "players.parquet", per_season=False),
        Dataset(
            "stats_player",
            "stats_player",
            "stats_player_week_{season}.parquet",
            per_season=True,
        ),
        Dataset("pbp", "pbp", "play_by_play_{season}.parquet", per_season=True),
        Dataset("injuries", "injuries", "injuries_{season}.parquet", per_season=True),
        Dataset("snap_counts", "snap_counts", "snap_counts_{season}.parquet", per_season=True),
        Dataset(
            "weekly_rosters", "weekly_rosters", "roster_weekly_{season}.parquet", per_season=True
        ),
        Dataset("depth_charts", "depth_charts", "depth_charts_{season}.parquet", per_season=True),
        # Richer sources for the prediction engine: per-play participation (who was on the field),
        # Pro Football Reference weekly advanced stats, and FTN's play charting.
        Dataset(
            "participation",
            "pbp_participation",
            "pbp_participation_{season}.parquet",
            per_season=True,
        ),
        Dataset(
            "advstats_pass", "pfr_advstats", "advstats_week_pass_{season}.parquet", per_season=True
        ),
        Dataset(
            "advstats_rush", "pfr_advstats", "advstats_week_rush_{season}.parquet", per_season=True
        ),
        Dataset(
            "advstats_rec", "pfr_advstats", "advstats_week_rec_{season}.parquet", per_season=True
        ),
        Dataset("ftn_charting", "ftn_charting", "ftn_charting_{season}.parquet", per_season=True),
        # Next Gen Stats: tracking-derived measures (separation, air yards share, rushing yards over
        # expected, completion percentage over expected). One file per area covering all seasons,
        # and unlike participation it is updated during the season.
        Dataset("ngs_receiving", "nextgen_stats", "ngs_receiving.parquet", per_season=False),
        Dataset("ngs_rushing", "nextgen_stats", "ngs_rushing.parquet", per_season=False),
        Dataset("ngs_passing", "nextgen_stats", "ngs_passing.parquet", per_season=False),
    )
}


def resolve_files(names: Iterable[str] | None, seasons: Iterable[int]) -> list[SourceFile]:
    """Expand dataset names (all datasets if None) and seasons into source files."""
    seasons = list(seasons)
    selected = list(DATASETS) if names is None else list(names)
    unknown = [name for name in selected if name not in DATASETS]
    if unknown:
        raise ValueError(f"unknown dataset(s): {', '.join(unknown)}; known: {', '.join(DATASETS)}")
    files: list[SourceFile] = []
    for name in selected:
        files.extend(DATASETS[name].files(seasons))
    return files
