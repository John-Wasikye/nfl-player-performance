from __future__ import annotations

import logging

import httpx
import pytest
from conftest import FakeGitHub, make_parquet

from nfl_pipeline import cli
from nfl_pipeline.publish import PublishSummary

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


# --- publish and run ----------------------------------------------------------------------------


@pytest.fixture
def steps(monkeypatch):
    """Replace dbt and publish with recorders so `run` can be tested without either."""
    calls: list[str] = []
    outcome = {"dbt": 0, "publish_error": None}

    def fake_dbt(_settings):
        calls.append("dbt")
        return outcome["dbt"]

    def fake_publish(_warehouse, _storage, *, now):
        calls.append("publish")
        if outcome["publish_error"]:
            raise cli.PublishError(outcome["publish_error"])
        return PublishSummary(season=2026, latest_week=2, files_written=7)

    monkeypatch.setattr(cli, "_run_dbt_build", fake_dbt)
    monkeypatch.setattr(cli, "publish", fake_publish)
    return calls, outcome


def serve_players(fake_host):
    fake_host.serve_timestamp("players", "t1")
    fake_host.serve(f"{BASE}/players/players.parquet", body=make_parquet())


def test_run_ingests_then_builds_then_publishes_in_order(fake_host, steps, capsys):
    calls, _ = steps
    serve_players(fake_host)

    code = cli.main(["run", "--datasets", "players"])

    assert code == 0
    assert calls == ["dbt", "publish"]
    assert "published season 2026 through week 2 (7 files)" in capsys.readouterr().out


def test_run_stops_before_dbt_when_the_ingest_fails(fake_host, steps, capsys, monkeypatch):
    calls, _ = steps
    monkeypatch.setenv("MAX_ATTEMPTS", "1")
    fake_host.serve(f"{BASE}/players/players.parquet", status=500)

    code = cli.main(["run", "--datasets", "players"])

    assert code == 1
    assert calls == []  # neither dbt nor publish ran
    assert "the ingest failed" in capsys.readouterr().err


def test_run_does_not_publish_when_dbt_tests_fail(fake_host, steps, capsys):
    calls, outcome = steps
    outcome["dbt"] = 1
    serve_players(fake_host)

    code = cli.main(["run", "--datasets", "players"])

    assert code == 1
    assert calls == ["dbt"]  # publish never ran
    assert "nothing was published" in capsys.readouterr().err


def test_run_reports_a_failed_publish(fake_host, steps, capsys):
    _, outcome = steps
    outcome["publish_error"] = "validation failed"
    serve_players(fake_host)

    code = cli.main(["run", "--datasets", "players"])

    assert code == 1
    assert "publish failed: validation failed" in capsys.readouterr().err


def test_run_refuses_non_local_storage_for_now(fake_host, steps, capsys, monkeypatch):
    calls, _ = steps
    monkeypatch.setenv("STORAGE_BACKEND", "s3")

    code = cli.main(["run"])

    assert code == 2
    assert calls == []
    assert "STORAGE_BACKEND=local" in capsys.readouterr().err


def test_publish_command_reports_a_missing_warehouse(fake_host, capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("WAREHOUSE_PATH", str(tmp_path / "missing.duckdb"))

    code = cli.main(["publish"])

    assert code == 1
    assert "warehouse not found" in capsys.readouterr().err


# --- backtest -----------------------------------------------------------------------------------


def test_backtest_writes_the_summary_and_a_report(tmp_path, monkeypatch, capsys):
    from test_backtest import build_warehouse

    warehouse = build_warehouse(tmp_path / "w.duckdb")
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "data"))
    report = tmp_path / "docs" / "backtest.md"

    code = cli.main(["backtest", "--report", str(report)])

    assert code == 0
    assert "# Backtest" in report.read_text(encoding="utf-8")
    assert (tmp_path / "data" / "backtest" / "summary.json").exists()
    assert "backtest done" in capsys.readouterr().out


def test_backtest_reports_a_warehouse_that_was_never_built(tmp_path, monkeypatch, capsys):
    import duckdb

    duckdb.connect(str(tmp_path / "w.duckdb")).close()
    monkeypatch.setenv("WAREHOUSE_PATH", str(tmp_path / "w.duckdb"))
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "data"))

    code = cli.main(["backtest", "--report", str(tmp_path / "r.md")])

    assert code == 1
    assert "backtest failed" in capsys.readouterr().err
