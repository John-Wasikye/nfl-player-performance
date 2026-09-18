from __future__ import annotations

import logging

import httpx
import pytest
from conftest import FakeGitHub, make_parquet

from nfl_pipeline import cli

BASE = "https://github.com/nflverse/nflverse-data/releases/download"


@pytest.fixture
def fake_host(monkeypatch, tmp_path):
    """Point the CLI at a fake nflverse host and a temporary local data directory."""
    github = FakeGitHub()
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "data"))
    real_client = httpx.Client  # keep a reference: cli.httpx is the same module object
    monkeypatch.setattr(
        cli.httpx,
        "Client",
        lambda **_kwargs: real_client(transport=httpx.MockTransport(github.handler)),
    )
    return github


def test_successful_ingest_returns_zero_and_prints_a_summary(fake_host, capsys, tmp_path):
    fake_host.serve_timestamp("players", "t1")
    fake_host.serve(f"{BASE}/players/players.parquet", body=make_parquet())

    code = cli.main(["ingest", "--datasets", "players"])

    assert code == 0
    assert "1 ingested" in capsys.readouterr().out
    assert list((tmp_path / "data" / "raw" / "players").rglob("players.parquet"))


def test_request_urls_are_not_logged(fake_host):
    fake_host.serve_timestamp("players", "t1")
    fake_host.serve(f"{BASE}/players/players.parquet", body=make_parquet())

    cli.main(["ingest", "--datasets", "players"])

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_failed_file_returns_nonzero_and_names_the_file(fake_host, capsys, monkeypatch):
    monkeypatch.setenv("MAX_ATTEMPTS", "1")
    fake_host.serve(f"{BASE}/players/players.parquet", status=500)

    code = cli.main(["ingest", "--datasets", "players"])

    assert code == 1
    assert "FAILED players/players.parquet" in capsys.readouterr().err


def test_unknown_dataset_is_a_usage_error(fake_host, capsys):
    code = cli.main(["ingest", "--datasets", "nope"])

    assert code == 2
    assert "unknown dataset" in capsys.readouterr().err


def test_bad_season_spec_is_a_usage_error(fake_host, capsys):
    code = cli.main(["ingest", "--seasons", "2025-2021"])

    assert code == 2
    assert "invalid season range" in capsys.readouterr().err


def test_seasons_option_selects_the_files(fake_host):
    for season in (2024, 2025):
        fake_host.serve(f"{BASE}/pbp/play_by_play_{season}.parquet", body=make_parquet())

    cli.main(["ingest", "--datasets", "pbp", "--seasons", "2024-2025"])

    assert f"{BASE}/pbp/play_by_play_2024.parquet" in fake_host.requests
    assert f"{BASE}/pbp/play_by_play_2025.parquet" in fake_host.requests
