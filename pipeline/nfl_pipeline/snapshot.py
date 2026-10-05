"""The warehouse snapshot: one writer, many read-only readers.

The daily task rebuilds the warehouse from raw on every run and never reads an earlier copy, so a
stale or corrupt file cannot turn into wrong output that looks fine. When the build succeeds it
uploads the finished file here. Ad-hoc tasks (backtest, experiment, predict) download it instead of
paying for a full rebuild.

Falling back to a rebuild is graceful, which is the problem: if the upload quietly broke, every
ad-hoc task would keep working, only slower, and nothing would say so. So each fallback logs a
warning carrying a fixed token. On AWS a CloudWatch metric filter counts that token and an alarm
watches the count; nothing in this module needs to know about CloudWatch.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

from nfl_pipeline.storage import Storage

logger = logging.getLogger("nfl_pipeline.snapshot")

SNAPSHOT_KEY = "warehouse/warehouse.duckdb"

# Fixed strings, searched for by the alarms in infra/. Change one and the alarm goes blind.
FALLBACK_TOKEN = "WAREHOUSE_SNAPSHOT_FALLBACK"
UPLOAD_FAILED_TOKEN = "WAREHOUSE_SNAPSHOT_UPLOAD_FAILED"


class SnapshotError(Exception):
    """The snapshot could not be uploaded."""


def publish_snapshot(warehouse: Path, raw: Storage) -> None:
    """Upload the finished warehouse. Raises SnapshotError, after logging it, on any failure."""
    try:
        raw.put_bytes(SNAPSHOT_KEY, Path(warehouse).read_bytes())
    except Exception as error:  # noqa: BLE001 - any failure to upload must be reported the same way
        logger.error("%s: %s: %s", UPLOAD_FAILED_TOKEN, type(error).__name__, error)
        raise SnapshotError(f"could not upload the warehouse snapshot: {error}") from error
    logger.info("uploaded the warehouse snapshot to %s", SNAPSHOT_KEY)


def _download(raw: Storage, destination: Path) -> str | None:
    """Fetch the snapshot to `destination`. Returns None on success, or the reason it failed."""
    try:
        data = raw.get_bytes(SNAPSHOT_KEY)
    except Exception as error:  # noqa: BLE001
        return f"{type(error).__name__}: {error}"
    if data is None:
        return "no snapshot has been uploaded"
    if not data:
        return "the snapshot is empty"
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".partial")
    partial.write_bytes(data)
    os.replace(partial, destination)
    return None


def ensure_warehouse(warehouse: Path, raw: Storage, rebuild: Callable[[], bool]) -> bool:
    """Make sure `warehouse` exists, preferring the snapshot over a rebuild.

    `rebuild` runs the dbt build and returns True on success. Returns whether a warehouse is now in
    place. A warehouse that is already on disk is used as it is.
    """
    warehouse = Path(warehouse)
    if warehouse.exists():
        return True
    reason = _download(raw, warehouse)
    if reason is None:
        logger.info("using the warehouse snapshot")
        return True
    logger.warning(
        "%s: rebuilding the warehouse from raw instead (%s). If this keeps happening, the "
        "snapshot upload at the end of the daily run is broken.",
        FALLBACK_TOKEN,
        reason,
    )
    return rebuild() and warehouse.exists()
