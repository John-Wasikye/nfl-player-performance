"""Settings, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from nfl_pipeline.storage import LocalStorage, S3Storage, Storage


@dataclass(frozen=True)
class Settings:
    storage_backend: str = "local"  # "local" or "s3"
    local_data_dir: Path = Path("data")
    s3_bucket: str = "nfl-data"
    s3_endpoint_url: str | None = None  # set for MinIO; leave unset for real AWS S3
    http_timeout: float = 60.0
    max_attempts: int = 3

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        return cls(
            storage_backend=env.get("STORAGE_BACKEND", "local"),
            local_data_dir=Path(env.get("LOCAL_DATA_DIR", "data")),
            s3_bucket=env.get("S3_BUCKET", "nfl-data"),
            s3_endpoint_url=env.get("S3_ENDPOINT_URL") or None,
            http_timeout=float(env.get("HTTP_TIMEOUT", "60")),
            max_attempts=int(env.get("MAX_ATTEMPTS", "3")),
        )


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_data_dir)
    if settings.storage_backend == "s3":
        return S3Storage(settings.s3_bucket, settings.s3_endpoint_url)
    raise ValueError(f"unknown STORAGE_BACKEND: {settings.storage_backend!r}")
