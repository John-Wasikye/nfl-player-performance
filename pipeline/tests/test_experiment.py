"""The weekly loop: evidence and verdict stay separate, and nothing ships itself."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nfl_pipeline.predict.experiment import ExperimentError, list_candidates, run_candidate
from nfl_pipeline.predict.proposals import REGISTRY


def test_every_registered_candidate_states_a_hypothesis():
    """A change with no stated reason cannot be shown to be wrong, so it is not an experiment."""
    for name, hypothesis in list_candidates():
        assert len(hypothesis) > 40, f"{name} has no real hypothesis"


def test_every_registered_candidate_declares_what_it_adds():
    for candidate in REGISTRY.values():
        assert candidate.adds, f"{candidate.name} declares no new columns"


def test_an_unknown_candidate_is_refused_by_name(tmp_path):
    with pytest.raises(ExperimentError, match="no candidate named"):
        run_candidate(
            tmp_path / "warehouse.duckdb",
            tmp_path / "ledger.json",
            "not_a_real_candidate",
            datetime.now(timezone.utc),
        )


def test_the_registry_is_keyed_by_the_candidates_own_name():
    """A mismatch would record one experiment under another's name in the ledger."""
    for key, candidate in REGISTRY.items():
        assert key == candidate.name


def test_the_shipped_candidate_is_a_legal_one():
    """The registered proposals must pass the same checks any new one would."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(0)
    rows = 120
    form = rng.gamma(4.0, 2.5, rows)
    frame = pd.DataFrame(
        {
            "player_id": [f"X{i}" for i in range(rows)],
            "season": 2025,
            "week": 4,
            "ppr_mean3": form,
            "ppr_mean5": form,
            "ppr_mean10": form,
            "ppr_season_avg": form,
            "actual_ppr": form,
        }
    )

    for candidate in REGISTRY.values():
        out = candidate.apply(frame)
        assert len(out) == rows
        for column in candidate.adds:
            assert column in out.columns


def test_a_candidate_dividing_by_a_zero_baseline_does_not_produce_infinity():
    """Plenty of players average zero, and an infinity is something a tree will happily split on."""
    import numpy as np
    import pandas as pd

    frame = pd.DataFrame(
        {
            "player_id": ["A", "B"],
            "season": [2025, 2025],
            "week": [4, 4],
            "ppr_mean3": [8.0, 8.0],
            "ppr_mean5": [8.0, 8.0],
            "ppr_mean10": [0.0, 4.0],
            "ppr_season_avg": [0.0, 4.0],
            "actual_ppr": [8.0, 8.0],
        }
    )

    out = REGISTRY["form_versus_baseline"].apply(frame)

    assert not np.isinf(out.form_versus_baseline).any()
    assert pd.isna(out.form_versus_baseline.iloc[0])
    assert out.form_versus_baseline.iloc[1] == pytest.approx(2.0)


def test_a_candidate_cannot_be_recorded_twice_on_the_same_day(tmp_path, monkeypatch):
    """The entry id is the date plus the name, and the ledger refuses a repeat."""
    from nfl_pipeline.predict.ledger import Ledger

    ledger = Ledger.load(tmp_path / "ledger.json")
    ledger.record(
        "2026-09-19-form_versus_baseline",
        "h",
        "c",
        {
            "promote": False,
            "reason": "already tested",
            "champion_mae": 4.5,
            "challenger_mae": 4.5,
            "improvement": 0.0,
        },
    )
    ledger.save()

    reloaded = Ledger.load(tmp_path / "ledger.json")
    with pytest.raises(ValueError, match="already in the ledger"):
        reloaded.record(
            "2026-09-19-form_versus_baseline",
            "h",
            "c",
            {
                "promote": True,
                "reason": "second try got lucky",
                "champion_mae": 4.5,
                "challenger_mae": 4.2,
                "improvement": 0.3,
            },
        )
