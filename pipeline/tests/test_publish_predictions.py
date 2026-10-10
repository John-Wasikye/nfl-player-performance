from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from nfl_pipeline.predict.run import PREDICTION_PREFIX, publish_predictions
from nfl_pipeline.storage import LocalStorage

NOW = datetime(2026, 10, 9, 15, 1, tzinfo=timezone.utc)


def projected_row(player_id, **overrides):
    row = {
        "player_id": player_id,
        "position_group": "WR",
        "display_name": player_id,
        "team": "KC",
        "opponent_team": "BUF",
        "is_home": True,
        "points": 12.0,
        "low": 4.0,
        "high": 20.0,
        "probability_of_playing": 1.0,
        "expected_points": 12.0,
        "injury_status": None,
        "status": "preliminary",
        "locked_at": None,
    }
    row.update(overrides)
    return row


def publish(tmp_path, rows):
    storage = LocalStorage(tmp_path)
    count = publish_predictions(
        storage,
        pd.DataFrame(rows),
        season=2026,
        week=5,
        model_version="test",
        now=NOW,
    )
    payload = json.loads(
        (tmp_path / PREDICTION_PREFIX / "2026" / "5" / "WR.json").read_text(encoding="utf-8")
    )
    return count, payload


def test_a_player_with_no_team_on_file_is_published_with_an_empty_team(tmp_path):
    # pandas fills a missing text value with NaN, which is truthy in Python, so `x or ""` keeps it.
    rows = [projected_row("p1", team=np.nan, opponent_team=np.nan)]

    _, payload = publish(tmp_path, rows)

    assert payload["players"][0]["team"] == ""
    assert payload["players"][0]["opponent"] == ""


def test_a_player_with_a_missing_opponent_does_not_stop_the_other_players(tmp_path):
    rows = [
        projected_row("p1", opponent_team=np.nan),
        projected_row("p2", team="BUF", opponent_team="KC"),
    ]

    _, payload = publish(tmp_path, rows)

    by_id = {player["player_id"]: player for player in payload["players"]}
    assert by_id["p1"]["opponent"] == ""
    assert by_id["p2"]["opponent"] == "KC"
