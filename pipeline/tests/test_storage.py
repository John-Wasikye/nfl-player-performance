import io

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
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

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
