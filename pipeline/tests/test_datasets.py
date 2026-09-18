import pytest

from nfl_pipeline.datasets import DATASETS, resolve_files


def test_per_season_dataset_expands_to_one_file_per_season():
    files = resolve_files(["pbp"], [2024, 2025])

    assert [file.filename for file in files] == [
        "play_by_play_2024.parquet",
        "play_by_play_2025.parquet",
    ]
    assert [file.season for file in files] == [2024, 2025]


def test_single_file_dataset_ignores_seasons():
    files = resolve_files(["schedules"], [2024, 2025])

    assert len(files) == 1
    assert files[0].filename == "games.parquet"
    assert files[0].season is None


def test_urls_point_at_the_release_download_location():
    (file,) = resolve_files(["stats_player"], [2026])

    assert file.url == (
        "https://github.com/nflverse/nflverse-data/releases/download/"
        "stats_player/stats_player_week_2026.parquet"
    )
    assert file.timestamp_url.endswith("/stats_player/timestamp.json")
    assert file.file_id == "stats_player/stats_player_week_2026.parquet"


def test_none_selects_every_dataset():
    files = resolve_files(None, [2026])

    assert {file.dataset for file in files} == set(DATASETS)


def test_unknown_dataset_is_rejected_with_the_known_names():
    with pytest.raises(ValueError, match="unknown dataset.*nope.*known:"):
        resolve_files(["nope"], [2026])
