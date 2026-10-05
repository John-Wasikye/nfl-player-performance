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

    def put_bytes_if_absent(self, key: str, data: bytes) -> bool:
        """Create the key only if nothing is there. True if written, False if it already existed.

        This is the write-once primitive. It must be atomic: two writers racing for the same key
        get exactly one True. It must never overwrite, which is why it is not `put_bytes` with a
        check in front of it.
        """
        ...

    def list_keys(self, prefix: str) -> list[str]:
        """Every key that starts with `prefix`, sorted."""
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

    def put_bytes_if_absent(self, key: str, data: bytes) -> bool:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL makes the create fail if the file exists, atomically. The temp-file-then-replace
        # used by put_bytes would do the opposite: os.replace overwrites.
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        return True

    def list_keys(self, prefix: str) -> list[str]:
        if prefix:
            _validate_key(prefix)
        keys = (
            path.relative_to(self._root).as_posix()
            for path in self._root.rglob("*")
            if path.is_file() and not path.name.endswith(".tmp")
        )
        return sorted(key for key in keys if key.startswith(prefix))


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

    def put_bytes_if_absent(self, key: str, data: bytes) -> bool:
        _validate_key(key)
        try:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data, IfNoneMatch="*")
        except ClientError as error:
            # 412 is "the key already exists". 409 means another write to the same key was in
            # flight; that is not an answer, so it is raised rather than guessed at.
            if error.response.get("Error", {}).get("Code") in {"PreconditionFailed", "412"}:
                return False
            raise
        return True

    def list_keys(self, prefix: str) -> list[str]:
        if prefix:
            _validate_key(prefix)
        keys: list[str] = []
        token = None
        while True:
            arguments: dict[str, Any] = {"Bucket": self._bucket, "Prefix": prefix}
            if token:
                arguments["ContinuationToken"] = token
            page = self._client.list_objects_v2(**arguments)
            keys.extend(item["Key"] for item in page.get("Contents", []))
            if not page.get("IsTruncated"):
                return sorted(keys)
            token = page["NextContinuationToken"]
