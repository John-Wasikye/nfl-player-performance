"""Ingest nflverse files into the raw layer of the data lake.

For each source file the ingest:
  1. checks the release's `timestamp.json` and skips the file if it has not
     changed since the last successful ingest,
  2. downloads it (retrying transient failures),
  3. validates that it is a non-empty Parquet file,
  4. stores it untouched under a dated raw key, and
  5. records the outcome in a run manifest.

Raw files are immutable snapshots: cleaning happens later, in dbt.
A failure on one file never stops the others, but the run reports it so the
caller can exit non-zero.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime

import httpx
import pyarrow as pa
import pyarrow.parquet as pq

from nfl_pipeline.datasets import SourceFile
from nfl_pipeline.storage import Storage

logger = logging.getLogger("nfl_pipeline.ingest")

STATE_KEY = "manifests/state.json"

INGESTED = "ingested"
SKIPPED_UNCHANGED = "skipped_unchanged"
NOT_AVAILABLE = "not_available"
FAILED = "failed"


class FetchError(Exception):
    """A download failed after retries (or with a non-retryable status)."""


class ValidationError(Exception):
    """A downloaded file is not a usable Parquet file."""


@dataclass
class FileResult:
    dataset: str
    filename: str
    season: int | None
    status: str
    source_last_updated: str | None = None
    key: str | None = None
    rows: int | None = None
    columns: int | None = None
    size_bytes: int | None = None
    sha256: str | None = None
    error: str | None = None


@dataclass
class RunManifest:
    run_id: str
    started_at: str
    finished_at: str | None = None
    results: list[FileResult] = field(default_factory=list)

    @property
    def failed(self) -> list[FileResult]:
        return [result for result in self.results if result.status == FAILED]

    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return asdict(self)


def _raw_key(source: SourceFile, ingest_date: str) -> str:
    parts = ["raw", source.dataset]
    if source.season is not None:
        parts.append(f"season={source.season}")
    parts.append(f"ingest_date={ingest_date}")
    parts.append(source.filename)
    return "/".join(parts)


def _fetch(
    client: httpx.Client,
    url: str,
    *,
    max_attempts: int,
    sleep: Callable[[float], None],
) -> httpx.Response | None:
    """GET a URL. Returns None on 404; retries 5xx, 429 and network errors."""
    last_error = "unknown error"
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.get(url)
        except httpx.TransportError as error:
            last_error = f"{type(error).__name__}: {error}"
        else:
            if response.status_code == 200:
                return response
            if response.status_code == 404:
                return None
            last_error = f"HTTP {response.status_code}"
            if response.status_code < 500 and response.status_code != 429:
                raise FetchError(f"{url}: {last_error}")
        if attempt < max_attempts:
            sleep(2 ** (attempt - 1))
    raise FetchError(f"{url}: {last_error} after {max_attempts} attempts")


def _validate_parquet(data: bytes) -> tuple[int, int]:
    """Return (rows, columns) for a non-empty Parquet file, or raise ValidationError."""
    try:
        metadata = pq.ParquetFile(io.BytesIO(data)).metadata
    except (pa.ArrowException, OSError) as error:
        raise ValidationError(f"not a valid Parquet file: {error}") from error
    if metadata.num_rows == 0:
        raise ValidationError("Parquet file has no rows")
    return metadata.num_rows, metadata.num_columns


def _read_state(storage: Storage) -> dict[str, dict]:
    raw = storage.get_bytes(STATE_KEY)
    return json.loads(raw) if raw else {}


def _source_timestamp(
    client: httpx.Client,
    source: SourceFile,
    cache: dict[str, str | None],
    *,
    max_attempts: int,
    sleep: Callable[[float], None],
) -> str | None:
    """The release's `last_updated` value, or None if it can't be read."""
    if source.timestamp_url not in cache:
        try:
            response = _fetch(client, source.timestamp_url, max_attempts=max_attempts, sleep=sleep)
            payload = response.json() if response is not None else {}
            cache[source.timestamp_url] = payload.get("last_updated")
        except (FetchError, ValueError) as error:
            logger.warning("could not read %s: %s", source.timestamp_url, error)
            cache[source.timestamp_url] = None
    return cache[source.timestamp_url]


def _ingest_one(
    source: SourceFile,
    *,
    storage: Storage,
    client: httpx.Client,
    state: dict[str, dict],
    timestamps: dict[str, str | None],
    ingest_date: str,
    now: datetime,
    force: bool,
    max_attempts: int,
    sleep: Callable[[float], None],
) -> FileResult:
    result = FileResult(source.dataset, source.filename, source.season, status=FAILED)
    try:
        last_updated = _source_timestamp(
            client, source, timestamps, max_attempts=max_attempts, sleep=sleep
        )
        result.source_last_updated = last_updated
        previous = state.get(source.file_id, {}).get("source_last_updated")
        if not force and last_updated is not None and last_updated == previous:
            result.status = SKIPPED_UNCHANGED
            return result

        response = _fetch(client, source.url, max_attempts=max_attempts, sleep=sleep)
        if response is None:
            result.status = NOT_AVAILABLE
            return result

        data = response.content
        result.rows, result.columns = _validate_parquet(data)
        result.size_bytes = len(data)
        result.sha256 = hashlib.sha256(data).hexdigest()
        result.key = _raw_key(source, ingest_date)
        storage.put_bytes(result.key, data)
        result.status = INGESTED
        state[source.file_id] = {
            "source_last_updated": last_updated,
            "key": result.key,
            "ingested_at": now.isoformat(),
        }
    except (FetchError, ValidationError) as error:
        result.error = str(error)
    return result


def ingest(
    files: Sequence[SourceFile],
    storage: Storage,
    client: httpx.Client,
    *,
    now: datetime,
    force: bool = False,
    max_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> RunManifest:
    """Ingest `files`, write the run manifest, and return it.

    `now` should be timezone-aware UTC. The ingest state (what was last
    ingested for each file) is only updated for files that succeeded, so a
    failed file is retried on the next run.
    """
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    manifest = RunManifest(run_id=run_id, started_at=now.isoformat())
    state = _read_state(storage)
    timestamps: dict[str, str | None] = {}
    ingest_date = now.strftime("%Y-%m-%d")

    for source in files:
        result = _ingest_one(
            source,
            storage=storage,
            client=client,
            state=state,
            timestamps=timestamps,
            ingest_date=ingest_date,
            now=now,
            force=force,
            max_attempts=max_attempts,
            sleep=sleep,
        )
        manifest.results.append(result)
        logger.info(
            "%s status=%s rows=%s error=%s",
            source.file_id
            if source.season is None
            else f"{source.file_id} (season {source.season})",
            result.status,
            result.rows,
            result.error,
        )

    storage.put_bytes(STATE_KEY, json.dumps(state, indent=2, sort_keys=True).encode())
    manifest.finished_at = datetime.now(now.tzinfo).isoformat()
    storage.put_bytes(
        f"manifests/runs/{run_id}.json",
        json.dumps(manifest.to_dict(), indent=2).encode(),
    )
    return manifest
