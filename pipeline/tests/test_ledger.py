"""The experiment ledger publishes failures as well as wins, and cannot be rewritten."""

from __future__ import annotations

import pytest

from nfl_pipeline.predict.ledger import Ledger


def decision(champion: float, challenger: float, promote: bool, reason: str = "") -> dict:
    return {
        "promote": promote,
        "reason": reason or ("beats the champion" if promote else "within the noise margin"),
        "champion_mae": champion,
        "challenger_mae": challenger,
        "improvement": round(champion - challenger, 4),
        "challenger_coverage": 0.80,
        "margin": 0.05,
    }


def test_a_rejected_experiment_is_recorded_just_like_a_winning_one(tmp_path):
    """The failures are the honest part. A ledger of only wins would be marketing."""
    ledger = Ledger.load(tmp_path / "ledger.json")

    ledger.record(
        entry_id="e1",
        hypothesis="snap share trend predicts a coming role change",
        change="added snap_share_delta3",
        decision=decision(4.50, 4.52, promote=False),
    )

    assert len(ledger.entries) == 1
    assert ledger.rejected[0].promoted is False


def test_an_experiment_result_cannot_be_replaced_by_a_luckier_rerun(tmp_path):
    ledger = Ledger.load(tmp_path / "ledger.json")
    ledger.record("e1", "h", "c", decision(4.50, 4.52, promote=False))

    with pytest.raises(ValueError, match="already in the ledger"):
        ledger.record("e1", "h", "c", decision(4.50, 4.30, promote=True))


def test_the_ledger_survives_a_round_trip(tmp_path):
    path = tmp_path / "ledger.json"
    ledger = Ledger.load(path)
    ledger.record("e1", "h", "c", decision(4.50, 4.40, promote=True))
    ledger.save()

    reloaded = Ledger.load(path)

    assert [e.entry_id for e in reloaded.entries] == ["e1"]
    assert reloaded.entries[0].improvement == pytest.approx(0.10)


def test_it_says_so_plainly_when_nothing_has_shipped(tmp_path):
    ledger = Ledger.load(tmp_path / "ledger.json")
    ledger.record("e1", "h", "c", decision(4.50, 4.52, promote=False))
    ledger.record("e2", "h", "c", decision(4.50, 4.55, promote=False))

    summary = ledger.summary()

    assert "none beat the current model" in summary
    assert "working as intended" in summary


def test_the_summary_counts_both_sides(tmp_path):
    ledger = Ledger.load(tmp_path / "ledger.json")
    ledger.record("e1", "h", "c", decision(4.50, 4.40, promote=True))
    ledger.record("e2", "h", "c", decision(4.40, 4.42, promote=False))

    summary = ledger.summary()

    assert "2 changes tested, 1 kept" in summary
    assert "other 1 were rejected" in summary


def test_an_empty_ledger_does_not_pretend_to_have_results(tmp_path):
    assert Ledger.load(tmp_path / "ledger.json").summary() == "No experiments have been graded yet."
