"""Settings, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from nfl_pipeline.predict.ledger import LEDGER_KEY
from nfl_pipeline.storage import LocalStorage, S3Storage, Storage


@dataclass(frozen=True)
class Settings:
    storage_backend: str = "local"  # "local" or "s3"
    local_data_dir: Path = Path("data")
    s3_bucket: str = "nfl-data"
    s3_endpoint_url: str | None = None  # set for MinIO; leave unset for real AWS S3
    http_timeout: float = 60.0
    max_attempts: int = 3
    warehouse_path: Path = Path("data/warehouse.duckdb")  # the dbt DuckDB database
    dbt_dir: Path = Path("dbt")  # the dbt project (also holds profiles.yml)
    # Locked predictions and the experiment ledger. Deliberately *not* under the warehouse or the
    # published data: both are rebuilt from scratch routinely, and these two must survive that.
    # A forecast that disappears when the warehouse is rebuilt cannot be graded honestly.
    # Locally they sit in `<local_data_dir>/predictions`. On AWS they get a bucket of their own,
    # versioned with Object Lock, because that is where "cannot be changed" is enforced.
    s3_records_bucket: str = "nfl-records"
    # The static site and the published JSON share one bucket, and so one CloudFront origin.
    s3_site_bucket: str = "nfl-site"
    ledger_key: str = LEDGER_KEY

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
            warehouse_path=Path(env.get("WAREHOUSE_PATH", "data/warehouse.duckdb")),
            dbt_dir=Path(env.get("DBT_DIR", "dbt")),
            s3_records_bucket=env.get("S3_RECORDS_BUCKET", "nfl-records"),
            s3_site_bucket=env.get("S3_SITE_BUCKET", "nfl-site"),
            ledger_key=env.get("LEDGER_KEY", LEDGER_KEY),
        )


def build_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_data_dir)
    if settings.storage_backend == "s3":
        return S3Storage(settings.s3_bucket, settings.s3_endpoint_url)
    raise ValueError(f"unknown STORAGE_BACKEND: {settings.storage_backend!r}")


def build_records_storage(settings: Settings) -> Storage:
    """Where the locked predictions and the ledger live: never the raw lake."""
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_data_dir / "predictions")
    if settings.storage_backend == "s3":
        return S3Storage(settings.s3_records_bucket, settings.s3_endpoint_url)
    raise ValueError(f"unknown STORAGE_BACKEND: {settings.storage_backend!r}")


def build_site_storage(settings: Settings) -> Storage:
    """Where the published JSON goes. Keys start with `data/v1`, locally and in the bucket alike."""
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_data_dir / "site")
    if settings.storage_backend == "s3":
        return S3Storage(settings.s3_site_bucket, settings.s3_endpoint_url)
    raise ValueError(f"unknown STORAGE_BACKEND: {settings.storage_backend!r}")


def dbt_raw_root(settings: Settings) -> str:
    """The `RAW_ROOT` dbt reads from. On S3 that is the bucket, so raw never lands on disk."""
    if settings.storage_backend == "local":
        return str(settings.local_data_dir / "raw")
    return f"s3://{settings.s3_bucket}/raw"


def dbt_target(settings: Settings) -> str:
    """`dev` for local files, `minio` when an endpoint is set, `aws` for real S3."""
    if settings.storage_backend == "local":
        return "dev"
    return "minio" if settings.s3_endpoint_url else "aws"
