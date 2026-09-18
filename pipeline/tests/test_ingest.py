from __future__ import annotations

import json

import httpx
from conftest import NOW, make_parquet

from nfl_pipeline.datasets import DATASETS, resolve_files
from nfl_pipeline.ingest import (
    FAILED,
    INGESTED,
    NOT_AVAILABLE,
    SKIPPED_UNCHANGED,
    STATE_KEY,
    ingest,
)

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
STATS_URL = f"{BASE}/stats_player/stats_player_regpost_2026.parquet"
PLAYERS_URL = f"{BASE}/players/players.parquet"


def run(files, storage, github, no_sleep, **kwargs):
    with github.client() as client:
        return ingest(files, storage, client, now=NOW, sleep=no_sleep, **kwargs)


def stats_files(*seasons):
    return resolve_files(["stats_player"], seasons or [2026])


def test_ingests_a_file_into_a_dated_raw_key(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "2026-09-18 09:46:17 EDT")
    github.serve(STATS_URL, body=make_parquet(rows=5))

    manifest = run(stats_files(), storage, github, no_sleep)

    (result,) = manifest.results
    assert result.status == INGESTED
    assert result.key == (
        "raw/stats_player/season=2026/ingest_date=2026-09-18/stats_player_regpost_2026.parquet"
    )
    assert result.rows == 5
    assert result.columns == 2
    assert result.source_last_updated == "2026-09-18 09:46:17 EDT"
    assert storage.get_bytes(result.key) == make_parquet(rows=5)
    assert not manifest.failed


def test_non_season_dataset_key_has_no_season_partition(github, storage, no_sleep):
    github.serve_timestamp("players", "2026-09-18 08:34:30 EDT")
    github.serve(PLAYERS_URL, body=make_parquet())

    manifest = run(resolve_files(["players"], [2026]), storage, github, no_sleep)

    assert manifest.results[0].key == "raw/players/ingest_date=2026-09-18/players.parquet"


def test_writes_run_manifest_and_state(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=make_parquet())

    manifest = run(stats_files(), storage, github, no_sleep)

    saved = json.loads(storage.get_bytes(f"manifests/runs/{manifest.run_id}.json"))
    assert saved["run_id"] == "20260918T153000Z"
    assert saved["results"][0]["status"] == INGESTED
    assert saved["results"][0]["sha256"]
    state = json.loads(storage.get_bytes(STATE_KEY))
    assert state["stats_player/stats_player_regpost_2026.parquet"]["source_last_updated"] == "t1"


def test_skips_unchanged_source_on_second_run(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=make_parquet())

    run(stats_files(), storage, github, no_sleep)
    second = run(stats_files(), storage, github, no_sleep)

    assert second.results[0].status == SKIPPED_UNCHANGED
    assert github.count(STATS_URL) == 1  # downloaded only once


def test_force_downloads_even_when_unchanged(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=make_parquet())

    run(stats_files(), storage, github, no_sleep)
    forced = run(stats_files(), storage, github, no_sleep, force=True)

    assert forced.results[0].status == INGESTED
    assert github.count(STATS_URL) == 2


def test_downloads_again_when_source_changes(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=make_parquet(rows=3))
    run(stats_files(), storage, github, no_sleep)

    github.serve_timestamp("stats_player", "t2")
    github.serve(STATS_URL, body=make_parquet(rows=4))
    second = run(stats_files(), storage, github, no_sleep)

    assert second.results[0].status == INGESTED
    assert second.results[0].rows == 4


def test_missing_file_is_not_available_not_a_failure(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")  # no file served, so the host returns 404

    manifest = run(stats_files(), storage, github, no_sleep)

    assert manifest.results[0].status == NOT_AVAILABLE
    assert not manifest.failed
    assert storage.get_bytes(STATE_KEY) == b"{}"  # nothing recorded, so it is tried again


def test_retries_server_errors_then_succeeds(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    calls = {"count": 0}
    payload = make_parquet()

    def flaky(request: httpx.Request) -> httpx.Response:
        if str(request.url) == STATS_URL:
            calls["count"] += 1
            if calls["count"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, content=payload)
        return github.handler(request)

    with httpx.Client(transport=httpx.MockTransport(flaky)) as client:
        manifest = ingest(stats_files(), storage, client, now=NOW, sleep=no_sleep)

    assert manifest.results[0].status == INGESTED
    assert calls["count"] == 3


def test_fails_after_exhausting_retries_without_recording_state(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, status=500)

    manifest = run(stats_files(), storage, github, no_sleep, max_attempts=3)

    (result,) = manifest.results
    assert result.status == FAILED
    assert "after 3 attempts" in result.error
    assert github.count(STATS_URL) == 3
    assert storage.get_bytes(STATE_KEY) == b"{}"


def test_client_errors_are_not_retried(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, status=403)

    manifest = run(stats_files(), storage, github, no_sleep)

    assert manifest.results[0].status == FAILED
    assert github.count(STATS_URL) == 1


def test_network_errors_are_retried_then_reported(storage, no_sleep):
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with httpx.Client(transport=httpx.MockTransport(broken)) as client:
        manifest = ingest(stats_files(), storage, client, now=NOW, sleep=no_sleep, max_attempts=2)

    assert manifest.results[0].status == FAILED
    assert "ConnectError" in manifest.results[0].error


def test_backoff_doubles_between_attempts(github, storage):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, status=500)
    delays: list[float] = []

    with github.client() as client:
        ingest(stats_files(), storage, client, now=NOW, sleep=delays.append, max_attempts=4)

    assert delays == [1, 2, 4]


def test_rejects_a_file_that_is_not_parquet(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=b"<html>rate limited</html>")

    manifest = run(stats_files(), storage, github, no_sleep)

    (result,) = manifest.results
    assert result.status == FAILED
    assert "not a valid Parquet" in result.error
    assert result.key is None
    assert storage.get_bytes(STATE_KEY) == b"{}"


def test_rejects_an_empty_parquet_file(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=make_parquet(rows=0))

    manifest = run(stats_files(), storage, github, no_sleep)

    assert manifest.results[0].status == FAILED
    assert "no rows" in manifest.results[0].error


def test_one_failure_does_not_stop_other_files(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve_timestamp("players", "t2")
    github.serve(STATS_URL, status=500)
    github.serve(PLAYERS_URL, body=make_parquet())
    files = resolve_files(["stats_player", "players"], [2026])

    manifest = run(files, storage, github, no_sleep, max_attempts=1)

    statuses = {result.dataset: result.status for result in manifest.results}
    assert statuses == {"stats_player": FAILED, "players": INGESTED}
    assert len(manifest.failed) == 1


def test_multiple_seasons_are_separate_files(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    for season in (2025, 2026):
        github.serve(
            f"{BASE}/stats_player/stats_player_regpost_{season}.parquet", body=make_parquet()
        )

    manifest = run(stats_files(2025, 2026), storage, github, no_sleep)

    assert [result.season for result in manifest.results] == [2025, 2026]
    assert all(result.status == INGESTED for result in manifest.results)
    assert github.count(f"{BASE}/stats_player/timestamp.json") == 1  # one lookup per release


def test_new_season_is_ingested_even_when_release_timestamp_is_unchanged(github, storage, no_sleep):
    github.serve_timestamp("stats_player", "t1")
    github.serve(STATS_URL, body=make_parquet())
    run(stats_files(2026), storage, github, no_sleep)

    github.serve(f"{BASE}/stats_player/stats_player_regpost_2025.parquet", body=make_parquet())
    second = run(stats_files(2025, 2026), storage, github, no_sleep)

    statuses = {result.season: result.status for result in second.results}
    assert statuses == {2025: INGESTED, 2026: SKIPPED_UNCHANGED}


def test_unreadable_timestamp_still_downloads(github, storage, no_sleep):
    github.serve(STATS_URL, body=make_parquet())  # timestamp.json returns 404

    manifest = run(stats_files(), storage, github, no_sleep)

    assert manifest.results[0].status == INGESTED
    assert manifest.results[0].source_last_updated is None


def test_every_registered_dataset_builds_a_download_url():
    files = resolve_files(None, [2026])

    assert len(files) == len(DATASETS)
    assert all(file.url.startswith("https://github.com/nflverse/nflverse-data/") for file in files)
