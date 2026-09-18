from __future__ import annotations

import json
from datetime import datetime, timezone

import duckdb
import pyarrow as pa
import pytest
from pydantic import ValidationError

from nfl_pipeline.contract import POSITIONS, RankingsFile
from nfl_pipeline.publish import DEFAULT_PREFIX, PublishError, publish
from nfl_pipeline.storage import LocalStorage

NOW = datetime(2026, 9, 18, 15, 30, tzinfo=timezone.utc)
RANKED_PER_POSITION = 10


def ranking_row(position, index, *, week, season=2026, ranked=True, **overrides):
    """One mart_rankings row. `index` (1-based) sets the player and, if ranked, the rank."""
    row = {
        "season": season,
        "week": week,
        "position_group": position,
        "player_id": f"{position}{index}",
        "display_name": f"{position} Player {index}",
        "team": "KC",
        "injury_status": None,
        "games": week,
        "is_qualified": ranked,
        "week_complete": True,
        "composite_score": 100.0 - index if ranked else None,
        "efficiency_score": 90.0 - index if ranked else None,
        "production_score": 80.0 - index if ranked else None,
        "composite_rank": index if ranked else None,
        "composite_rank_prev": index if ranked and week > 1 else None,
        "composite_movement": 0 if ranked and week > 1 else None,
        "composite_is_new": False,
        "ppr_points": 200.0 - index,
        "ppr_per_game": (200.0 - index) / week,
        "fantasy_rank": index,
        "fantasy_rank_prev": index if week > 1 else None,
        "fantasy_movement": 0 if week > 1 else None,
        "fantasy_is_new": False,
    }
    row.update(overrides)
    return row


def all_rankings(weeks=(1, 2)):
    rows = []
    for week in weeks:
        for position in POSITIONS:
            for index in range(1, RANKED_PER_POSITION + 1):
                rows.append(ranking_row(position, index, week=week))
            # one player with too little volume: listed but not ranked
            rows.append(
                ranking_row(
                    position,
                    RANKED_PER_POSITION + 1,
                    week=week,
                    ranked=False,
                    fantasy_rank=RANKED_PER_POSITION + 1,
                )
            )
    return rows


def make_warehouse(path, rankings=None, breakdown=None):
    rankings = all_rankings() if rankings is None else rankings
    breakdown = breakdown if breakdown is not None else [
        {
            "season": 2026, "week": 2, "position_group": "QB", "player_id": "QB1",
            "metric": "epa_per_dropback", "component": "efficiency", "metric_value": 0.21,
            "percentile": 0.9, "weight": 1.0, "contribution_points": 12.6,
        },
        {
            "season": 2026, "week": 2, "position_group": "QB", "player_id": "QB1",
            "metric": "passing_yards", "component": "production", "metric_value": 512.0,
            "percentile": 0.8, "weight": 1.0, "contribution_points": 6.0,
        },
    ]  # fmt: skip
    connection = duckdb.connect(str(path))
    for name, rows in (("mart_rankings", rankings), ("mart_ranking_breakdown", breakdown)):
        if rows:
            connection.register("staged", pa.Table.from_pylist(rows))
            connection.execute(f"create table {name} as select * from staged")
            connection.unregister("staged")
    connection.execute(
        "create table ranking_config as select * from (values "
        + ", ".join(f"('{p}', 14.0, 0.7, 0.3)" for p in POSITIONS)
        + ") t(position_group, min_role_per_week, efficiency_weight, production_weight)"
    )
    connection.execute(
        "create table ranking_weights as select * from (values "
        "('QB', 'epa_per_dropback', 'efficiency', 'higher', 1.0), "
        "('QB', 'sack_rate', 'efficiency', 'lower', 1.0), "
        "('QB', 'passing_yards', 'production', 'higher', 1.0)"
        ") t(position_group, metric, component, direction, weight)"
    )
    connection.close()
    return path


@pytest.fixture
def warehouse(tmp_path):
    return make_warehouse(tmp_path / "warehouse.duckdb")


@pytest.fixture
def lake(tmp_path):
    return LocalStorage(tmp_path / "lake")


def read_json(storage, key):
    return json.loads(storage.get_bytes(f"{DEFAULT_PREFIX}/{key}"))


class RecordingStorage(LocalStorage):
    def __init__(self, root):
        super().__init__(root)
        self.writes: list[str] = []

    def put_bytes(self, key, data):
        self.writes.append(key)
        super().put_bytes(key, data)


def test_publishes_the_full_set_of_files(warehouse, lake):
    summary = publish(warehouse, lake, now=NOW)

    assert summary.season == 2026
    assert summary.latest_week == 2
    for week in (1, 2):
        for position in POSITIONS:
            assert lake.get_bytes(f"{DEFAULT_PREFIX}/rankings/2026/{week}/{position}.json")
    assert lake.get_bytes(f"{DEFAULT_PREFIX}/players/QB1.json")
    assert lake.get_bytes(f"{DEFAULT_PREFIX}/movers/2026/2.json")
    assert lake.get_bytes(f"{DEFAULT_PREFIX}/methodology.json")
    # 10 weeks-of-rankings + 55 players + movers + methodology + meta
    assert summary.files_written == 2 * 5 + 5 * (RANKED_PER_POSITION + 1) + 3


def test_meta_is_written_last(warehouse, tmp_path):
    storage = RecordingStorage(tmp_path / "lake")

    publish(warehouse, storage, now=NOW)

    assert storage.writes[-1] == f"{DEFAULT_PREFIX}/meta.json"
    assert storage.writes.count(f"{DEFAULT_PREFIX}/meta.json") == 1


def test_meta_describes_the_published_data(warehouse, lake):
    lake.put_bytes(
        "manifests/state.json",
        json.dumps(
            {
                "stats_player/stats_player_week_2026.parquet": {
                    "source_last_updated": "2026-09-18 09:46:17 EDT",
                    "ingested_at": "2026-09-18T15:00:00+00:00",
                }
            }
        ).encode(),
    )

    publish(warehouse, lake, now=NOW)

    meta = read_json(lake, "meta.json")
    assert meta["season"] == 2026
    assert meta["latest_week"] == 2
    assert meta["weeks"] == [1, 2]
    assert meta["week_complete"] is True
    assert meta["positions"] == ["QB", "RB", "WR", "TE", "K"]
    assert meta["generated_at"] == NOW.isoformat()
    assert meta["data_as_of"] == {"stats_player": "2026-09-18 09:46:17 EDT"}


def test_ranked_players_come_first_then_the_unranked(warehouse, lake):
    publish(warehouse, lake, now=NOW)

    players = read_json(lake, "rankings/2026/2/QB.json")["players"]

    ranks = [p["composite"]["rank"] for p in players]
    assert ranks[:RANKED_PER_POSITION] == list(range(1, RANKED_PER_POSITION + 1))
    assert ranks[RANKED_PER_POSITION:] == [None]
    assert players[-1]["qualified"] is False
    assert players[-1]["composite"]["score"] is None


def test_publishing_is_deterministic(warehouse, tmp_path):
    first, second = LocalStorage(tmp_path / "a"), LocalStorage(tmp_path / "b")

    publish(warehouse, first, now=NOW)
    publish(warehouse, second, now=NOW)

    for path in (tmp_path / "a").rglob("*.json"):
        other = tmp_path / "b" / path.relative_to(tmp_path / "a")
        assert path.read_bytes() == other.read_bytes(), path.name


def test_player_file_has_history_and_the_latest_breakdown(warehouse, lake):
    publish(warehouse, lake, now=NOW)

    player = read_json(lake, "players/QB1.json")

    assert player["name"] == "QB Player 1"
    assert player["position"] == "QB"
    assert [week["week"] for week in player["history"]] == [1, 2]
    assert [item["metric"] for item in player["breakdown"]] == ["epa_per_dropback", "passing_yards"]
    assert read_json(lake, "players/QB2.json")["breakdown"] == []


def test_movers_lists_the_biggest_risers_and_fallers(tmp_path, lake):
    rows = all_rankings()
    for row in rows:
        if row["week"] == 2 and row["position_group"] == "QB" and row["composite_rank"]:
            row["composite_movement"] = {1: 4, 2: -3, 3: 1}.get(row["composite_rank"], 0)
    warehouse = make_warehouse(tmp_path / "w.duckdb", rankings=rows)

    publish(warehouse, lake, now=NOW)

    movers = read_json(lake, "movers/2026/2.json")
    assert [m["player_id"] for m in movers["risers"]["QB"]] == ["QB1", "QB3"]
    assert [m["player_id"] for m in movers["fallers"]["QB"]] == ["QB2"]
    assert movers["risers"]["RB"] == []  # nobody moved


def test_methodology_lists_the_settings_in_use(warehouse, lake):
    publish(warehouse, lake, now=NOW)

    methodology = read_json(lake, "methodology.json")

    qb = methodology["positions"][0]
    assert qb["position"] == "QB"
    assert qb["efficiency_weight"] == 0.7 and qb["production_weight"] == 0.3
    assert {m["metric"]: m["direction"] for m in qb["metrics"]} == {
        "epa_per_dropback": "higher",
        "sack_rate": "lower",
        "passing_yards": "higher",
    }
    assert methodology["backtest"] is None


# --- the validation gate: bad data must never be published -----------------------------------


def published_anything(tmp_path) -> bool:
    return any((tmp_path / "lake").rglob("*.json")) if (tmp_path / "lake").exists() else False


def test_duplicate_ranks_block_the_publish(tmp_path, lake):
    rows = all_rankings()
    for row in rows:
        if row["week"] == 2 and row["position_group"] == "QB" and row["composite_rank"] == 2:
            row["composite_rank"] = 1  # two players tied at rank 1
    warehouse = make_warehouse(tmp_path / "w.duckdb", rankings=rows)

    with pytest.raises(PublishError, match="composite ranks"):
        publish(warehouse, lake, now=NOW)

    assert not published_anything(tmp_path)


def test_too_few_ranked_players_blocks_the_publish(tmp_path, lake):
    rows = [
        r
        for r in all_rankings()
        if not (r["week"] == 2 and r["position_group"] == "RB" and r["fantasy_rank"] > 3)
    ]
    warehouse = make_warehouse(tmp_path / "w.duckdb", rankings=rows)

    with pytest.raises(PublishError, match="only 3 ranked players"):
        publish(warehouse, lake, now=NOW)

    assert not published_anything(tmp_path)


def test_a_score_outside_0_to_100_blocks_the_publish(tmp_path, lake):
    rows = all_rankings()
    rows[0]["composite_score"] = 140.0
    warehouse = make_warehouse(tmp_path / "w.duckdb", rankings=rows)

    with pytest.raises(PublishError, match="contract"):
        publish(warehouse, lake, now=NOW)

    assert not published_anything(tmp_path)


def test_an_unranked_player_with_a_score_blocks_the_publish(tmp_path, lake):
    rows = all_rankings()
    unranked = next(r for r in rows if not r["is_qualified"])
    unranked["composite_score"] = 50.0
    warehouse = make_warehouse(tmp_path / "w.duckdb", rankings=rows)

    with pytest.raises(PublishError, match="unranked but has a score"):
        publish(warehouse, lake, now=NOW)


def test_a_missing_warehouse_is_reported(tmp_path, lake):
    with pytest.raises(PublishError, match="warehouse not found"):
        publish(tmp_path / "nope.duckdb", lake, now=NOW)


def test_an_empty_rankings_table_is_reported(tmp_path, lake):
    warehouse = make_warehouse(tmp_path / "w.duckdb", rankings=[ranking_row("QB", 1, week=1)])
    connection = duckdb.connect(str(warehouse))
    connection.execute("delete from mart_rankings")
    connection.close()

    with pytest.raises(PublishError, match="empty"):
        publish(warehouse, lake, now=NOW)


def test_a_failed_publish_leaves_the_previous_data_untouched(tmp_path, lake):
    good = make_warehouse(tmp_path / "good.duckdb")
    publish(good, lake, now=NOW)
    before = lake.get_bytes(f"{DEFAULT_PREFIX}/meta.json")

    rows = all_rankings()
    rows[0]["composite_score"] = -5.0
    bad = make_warehouse(tmp_path / "bad.duckdb", rankings=rows)
    with pytest.raises(PublishError):
        publish(bad, lake, now=datetime(2026, 9, 19, tzinfo=timezone.utc))

    assert lake.get_bytes(f"{DEFAULT_PREFIX}/meta.json") == before


def test_the_contract_rejects_unknown_fields_and_bad_values():
    with pytest.raises(ValidationError):
        RankingsFile.model_validate(
            {
                "schema_version": 1, "season": 2026, "week": 1, "position": "QB",
                "week_complete": True, "players": [], "surprise": 1,
            }
        )  # fmt: skip
    with pytest.raises(ValidationError):
        RankingsFile.model_validate(
            {
                "schema_version": 1, "season": 2026, "week": 1, "position": "LB",
                "week_complete": True, "players": [],
            }
        )  # fmt: skip


def test_methodology_includes_the_backtest_headline_when_one_has_been_run(warehouse, lake):
    lake.put_bytes(
        "backtest/summary.json",
        json.dumps(
            {
                "generated_at": "2026-09-18T00:00:00+00:00",
                "seasons": {"tune": [2021, 2022], "test": [2023]},
                "selected_efficiency_weight": 0.2,
                "current_efficiency_weight": 0.7,
                "results": {
                    "points": {
                        "test": {
                            method: {
                                "positions": {
                                    position: {"spearman": value} for position in POSITIONS
                                }
                            }
                            for method, value in (
                                ("composite_020", 0.30),
                                ("composite_070", 0.22),
                                ("ppr_per_game", 0.31),
                            )
                        }
                    }
                },
            }
        ).encode(),
    )

    publish(warehouse, lake, now=NOW)

    backtest = read_json(lake, "methodology.json")["backtest"]
    assert backtest["selected_efficiency_weight"] == 0.2
    assert backtest["held_out_seasons"] == [2023]
    assert backtest["held_out_spearman"]["QB"] == {
        "selected": 0.30,
        "current": 0.22,
        "points_per_game_baseline": 0.31,
    }


def test_an_unreadable_backtest_summary_is_ignored_not_fatal(warehouse, lake):
    lake.put_bytes("backtest/summary.json", b"not json at all")

    publish(warehouse, lake, now=NOW)

    assert read_json(lake, "methodology.json")["backtest"] is None
