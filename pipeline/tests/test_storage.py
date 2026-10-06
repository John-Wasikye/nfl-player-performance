import io
import tempfile
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from nfl_pipeline.config import Settings, build_storage
from nfl_pipeline.storage import LocalStorage, S3Storage


def test_local_round_trip_creates_nested_directories(tmp_path):
    storage = LocalStorage(tmp_path)

    storage.put_bytes("raw/players/ingest_date=2026-09-18/players.parquet", b"data")

    assert storage.get_bytes("raw/players/ingest_date=2026-09-18/players.parquet") == b"data"


def test_local_missing_key_returns_none(tmp_path):
    assert LocalStorage(tmp_path).get_bytes("nope.json") is None


def test_local_overwrite_replaces_content_and_leaves_no_temp_file(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.put_bytes("a/b.txt", b"one")
    storage.put_bytes("a/b.txt", b"two")

    assert storage.get_bytes("a/b.txt") == b"two"
    assert [path.name for path in (tmp_path / "a").iterdir()] == ["b.txt"]


@pytest.mark.parametrize("key", ["", "/etc/passwd", "../outside", "a/../../outside"])
def test_local_rejects_keys_that_escape_the_root(tmp_path, key):
    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).put_bytes(key, b"x")


class FakeS3Client:
    """Behaves like S3 where the project depends on it: conditional writes and paged listings."""

    page_size = 2  # small on purpose, so pagination is exercised by every listing test

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.content_types: dict[tuple[str, str], str | None] = {}

    def put_object(self, Bucket, Key, Body, IfNoneMatch=None, ContentType=None):
        if IfNoneMatch == "*" and (Bucket, Key) in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.objects[(Bucket, Key)] = Body
        self.content_types[(Bucket, Key)] = ContentType

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None):
        keys = sorted(k for b, k in self.objects if b == Bucket and k.startswith(Prefix))
        start = int(ContinuationToken) if ContinuationToken else 0
        page = keys[start : start + self.page_size]
        more = start + self.page_size < len(keys)
        response = {"Contents": [{"Key": key} for key in page], "IsTruncated": more}
        if more:
            response["NextContinuationToken"] = str(start + self.page_size)
        return response

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


def test_s3_round_trip_uses_the_configured_bucket():
    client = FakeS3Client()
    storage = S3Storage("nfl-data", client=client)

    storage.put_bytes("manifests/state.json", b"{}")

    assert client.objects == {("nfl-data", "manifests/state.json"): b"{}"}
    assert storage.get_bytes("manifests/state.json") == b"{}"


def test_s3_missing_key_returns_none():
    assert S3Storage("nfl-data", client=FakeS3Client()).get_bytes("missing") is None


def test_s3_other_errors_are_raised():
    class Denied(FakeS3Client):
        def get_object(self, Bucket, Key):
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")

    with pytest.raises(ClientError):
        S3Storage("nfl-data", client=Denied()).get_bytes("x")


def test_settings_defaults_to_local_storage():
    settings = Settings.from_env({})

    assert settings.storage_backend == "local"
    assert isinstance(build_storage(settings), LocalStorage)


def test_settings_read_s3_configuration_from_env():
    settings = Settings.from_env(
        {
            "STORAGE_BACKEND": "s3",
            "S3_BUCKET": "my-bucket",
            "S3_ENDPOINT_URL": "http://minio:9000",
            "MAX_ATTEMPTS": "5",
        }
    )

    assert settings.s3_bucket == "my-bucket"
    assert settings.s3_endpoint_url == "http://minio:9000"
    assert settings.max_attempts == 5


def test_unknown_storage_backend_is_rejected():
    with pytest.raises(ValueError, match="unknown STORAGE_BACKEND"):
        build_storage(Settings(storage_backend="ftp"))


# The write-once contract. Every backend is held to the same assertions, because the locked
# predictions are only worth anything if a second write really is refused. A fake that quietly
# overwrote would make the whole design look sound while proving nothing.


def check_write_once_contract(storage) -> None:
    assert storage.put_bytes_if_absent("locks/2026/week_01.json", b"first") is True
    assert storage.put_bytes_if_absent("locks/2026/week_01.json", b"second") is False
    assert storage.get_bytes("locks/2026/week_01.json") == b"first"

    # Identical bytes are refused too: the caller decides whether that is a harmless retry.
    assert storage.put_bytes_if_absent("locks/2026/week_01.json", b"first") is False

    assert storage.put_bytes_if_absent("locks/2026/week_02.json", b"other") is True


def check_listing_contract(storage) -> None:
    for key in ["locks/2026/week_03.json", "locks/2026/week_01.json", "locks/2025/week_18.json"]:
        storage.put_bytes(key, b"x")
    storage.put_bytes("ledger.json", b"x")
    storage.put_bytes("locks/2026/week_02.json", b"x")
    storage.put_bytes("locks/2026/week_04.json", b"x")

    assert storage.list_keys("locks/2026/") == [
        "locks/2026/week_01.json",
        "locks/2026/week_02.json",
        "locks/2026/week_03.json",
        "locks/2026/week_04.json",
    ]
    assert storage.list_keys("locks/") == sorted(storage.list_keys("locks/"))
    assert len(storage.list_keys("locks/")) == 5
    assert storage.list_keys("nothing/here/") == []


@pytest.fixture(params=["local", "s3"])
def backend(request, tmp_path):
    if request.param == "local":
        return LocalStorage(tmp_path)
    return S3Storage("records", client=FakeS3Client())


def test_every_backend_refuses_a_second_write(backend):
    check_write_once_contract(backend)


def test_every_backend_lists_what_was_written_in_order(backend):
    check_listing_contract(backend)


def test_a_failed_conditional_write_leaves_no_temp_file_behind(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.put_bytes_if_absent("a.json", b"one")
    storage.put_bytes_if_absent("a.json", b"two")

    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]


def test_s3_conditional_write_is_sent_with_if_none_match():
    seen = {}

    class Recording(FakeS3Client):
        def put_object(self, **arguments):
            seen.update(arguments)
            super().put_object(**arguments)

    S3Storage("records", client=Recording()).put_bytes_if_absent("k", b"v")

    assert seen["IfNoneMatch"] == "*"


def test_s3_conditional_write_raises_on_errors_other_than_already_exists():
    class Denied(FakeS3Client):
        def put_object(self, **arguments):
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")

    with pytest.raises(ClientError):
        S3Storage("records", client=Denied()).put_bytes_if_absent("k", b"v")


def test_the_contract_actually_catches_a_backend_that_overwrites():
    class Overwrites(LocalStorage):
        def put_bytes_if_absent(self, key, data):
            self.put_bytes(key, data)
            return True

    with pytest.raises(AssertionError):
        check_write_once_contract(Overwrites(Path(tempfile.mkdtemp())))


def test_json_is_stored_with_a_json_content_type_and_other_keys_are_left_alone():
    client = FakeS3Client()
    storage = S3Storage("b", client=client)

    storage.put_bytes("data/v1/meta.json", b"{}")
    assert storage.put_bytes_if_absent("2026/week_01.json", b"{}")
    storage.put_bytes("warehouse/warehouse.duckdb", b"x")

    assert client.content_types[("b", "data/v1/meta.json")] == "application/json"
    assert client.content_types[("b", "2026/week_01.json")] == "application/json"
    assert client.content_types[("b", "warehouse/warehouse.duckdb")] is None
