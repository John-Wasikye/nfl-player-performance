"""Storage backends.

The pipeline only needs to write and read small blobs by key, so storage is a
tiny interface with two implementations: the local filesystem (tests and quick
local runs) and S3-compatible object storage (MinIO in Docker, S3 on AWS).
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

import boto3
from botocore.exceptions import ClientError


class Storage(Protocol):
    def put_bytes(self, key: str, data: bytes) -> None: ...

    def get_bytes(self, key: str) -> bytes | None:
        """Return the stored bytes, or None if the key does not exist."""
        ...


def _validate_key(key: str) -> None:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"invalid storage key: {key!r}")


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        _validate_key(key)
        return self._root / Path(*PurePosixPath(key).parts)

    def put_bytes(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # atomic: readers never see a half-written file

    def get_bytes(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None


class S3Storage:
    def __init__(
        self, bucket: str, endpoint_url: str | None = None, client: Any | None = None
    ) -> None:
        self._bucket = bucket
        self._client = client or boto3.client("s3", endpoint_url=endpoint_url)

    def put_bytes(self, key: str, data: bytes) -> None:
        _validate_key(key)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get_bytes(self, key: str) -> bytes | None:
        _validate_key(key)
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                return None
            raise
        return response["Body"].read()
