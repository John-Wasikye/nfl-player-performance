import logging

import pytest
from test_storage import FakeS3Client

from nfl_pipeline.snapshot import (
    FALLBACK_TOKEN,
    SNAPSHOT_KEY,
    UPLOAD_FAILED_TOKEN,
    SnapshotError,
    ensure_warehouse,
    publish_snapshot,
)
from nfl_pipeline.storage import S3Storage


@pytest.fixture
def raw():
    return S3Storage("raw", client=FakeS3Client())


def rebuilder(path, calls, succeeds=True):
    def rebuild():
        calls.append("rebuild")
        if succeeds:
            path.write_bytes(b"rebuilt")
        return succeeds

    return rebuild


def test_an_upload_followed_by_a_download_returns_the_same_file(raw, tmp_path):
    source = tmp_path / "a.duckdb"
    source.write_bytes(b"warehouse")
    publish_snapshot(source, raw)
    calls = []

    assert ensure_warehouse(tmp_path / "b.duckdb", raw, rebuilder(tmp_path / "b.duckdb", calls))

    assert (tmp_path / "b.duckdb").read_bytes() == b"warehouse"
    assert calls == []


def test_a_warehouse_already_on_disk_is_used_as_it_is(raw, tmp_path):
    local = tmp_path / "w.duckdb"
    local.write_bytes(b"mine")
    calls = []

    assert ensure_warehouse(local, raw, rebuilder(local, calls))

    assert local.read_bytes() == b"mine"
    assert calls == []


def test_a_missing_snapshot_rebuilds_and_says_so_with_the_alarm_token(raw, tmp_path, caplog):
    target = tmp_path / "w.duckdb"
    calls = []

    with caplog.at_level(logging.WARNING, logger="nfl_pipeline.snapshot"):
        ok = ensure_warehouse(target, raw, rebuilder(target, calls))

    assert ok and calls == ["rebuild"]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert FALLBACK_TOKEN in warnings[0].getMessage()
    assert "no snapshot has been uploaded" in warnings[0].getMessage()


def test_an_unreadable_snapshot_falls_back_with_the_reason_instead_of_crashing(tmp_path, caplog):
    class Denied(FakeS3Client):
        def get_object(self, Bucket, Key):
            raise RuntimeError("AccessDenied")

    target = tmp_path / "w.duckdb"
    calls = []

    with caplog.at_level(logging.WARNING, logger="nfl_pipeline.snapshot"):
        ok = ensure_warehouse(target, S3Storage("raw", client=Denied()), rebuilder(target, calls))

    assert ok and calls == ["rebuild"]
    assert "AccessDenied" in caplog.text and FALLBACK_TOKEN in caplog.text


def test_an_empty_snapshot_is_not_trusted(raw, tmp_path, caplog):
    raw.put_bytes(SNAPSHOT_KEY, b"")
    target = tmp_path / "w.duckdb"
    calls = []

    with caplog.at_level(logging.WARNING, logger="nfl_pipeline.snapshot"):
        ensure_warehouse(target, raw, rebuilder(target, calls))

    assert calls == ["rebuild"]
    assert target.read_bytes() == b"rebuilt"


def test_every_fallback_is_logged_so_a_metric_filter_can_count_them(raw, tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="nfl_pipeline.snapshot"):
        for index in range(3):
            target = tmp_path / f"w{index}.duckdb"
            ensure_warehouse(target, raw, rebuilder(target, []))

    assert caplog.text.count(FALLBACK_TOKEN) == 3


def test_a_failed_rebuild_reports_no_warehouse(raw, tmp_path):
    target = tmp_path / "w.duckdb"

    assert not ensure_warehouse(target, raw, rebuilder(target, [], succeeds=False))


def test_a_failed_upload_is_logged_with_its_token_and_raised(tmp_path, caplog):
    class Denied(FakeS3Client):
        def put_object(self, **arguments):
            raise RuntimeError("AccessDenied")

    source = tmp_path / "a.duckdb"
    source.write_bytes(b"x")

    with (
        caplog.at_level(logging.ERROR, logger="nfl_pipeline.snapshot"),
        pytest.raises(SnapshotError, match="AccessDenied"),
    ):
        publish_snapshot(source, S3Storage("raw", client=Denied()))

    assert UPLOAD_FAILED_TOKEN in caplog.text
