from __future__ import annotations

import io
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from nfl_pipeline.storage import LocalStorage

NOW = datetime(2026, 9, 18, 15, 30, tzinfo=timezone.utc)


def make_parquet(rows: int = 3) -> bytes:
    table = pa.table({"player_id": list(range(rows)), "value": [float(i) for i in range(rows)]})
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


class FakeGitHub:
    """A fake nflverse release host that records every request it receives."""

    def __init__(self) -> None:
        self.responses: dict[str, tuple[int, bytes]] = {}
        self.requests: list[str] = []

    def serve(self, url: str, status: int = 200, body: bytes = b"") -> None:
        self.responses[url] = (status, body)

    def serve_timestamp(self, tag: str, last_updated: str) -> None:
        self.serve(
            f"https://github.com/nflverse/nflverse-data/releases/download/{tag}/timestamp.json",
            body=f'{{"last_updated": "{last_updated}"}}'.encode(),
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.requests.append(url)
        status, body = self.responses.get(url, (404, b""))
        return httpx.Response(status, content=body)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def count(self, url: str) -> int:
        return self.requests.count(url)


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path / "lake")


@pytest.fixture
def no_sleep() -> Callable[[float], None]:
    return lambda _seconds: None
