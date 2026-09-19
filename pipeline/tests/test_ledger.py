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
    assert reloaded.entries[0].champion_score == pytest.approx(4.50)


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
    assert "the other one was rejected" in summary


def test_the_summary_never_adds_up_scores_from_different_metrics(tmp_path):
    """Mean error and margin-over-baseline are different quantities on different populations.

    Summing them would produce a tidy figure that means nothing, which is the exact mistake the
    ledger exists to prevent, so the summary reports counts and leaves the numbers to the rows.
    """
    ledger = Ledger.load(tmp_path / "ledger.json")
    ledger.record("e1", "h", "c", decision(4.50, 4.40, promote=True))
    ledger.record("e2", "h", "c", decision(0.05, 0.16, promote=True), metric="margin_over_baseline")

    summary = ledger.summary()

    assert "2 changes tested, 2 kept" in summary
    assert "every one of them was kept" in summary
    assert "0.1" not in summary


def test_an_experiment_that_changes_the_population_records_which_metric_judged_it(tmp_path):
    """Mean error is not comparable across populations, so such an entry must say what it used."""
    ledger = Ledger.load(tmp_path / "ledger.json")

    entry = ledger.record(
        "e1", "h", "c", decision(0.05, 0.16, promote=True), metric="margin_over_baseline"
    )

    assert entry.metric == "margin_over_baseline"


def test_an_ordinary_entry_is_judged_on_mean_error(tmp_path):
    ledger = Ledger.load(tmp_path / "ledger.json")

    assert ledger.record("e1", "h", "c", decision(4.5, 4.4, promote=True)).metric == "mae"


def test_an_empty_ledger_does_not_pretend_to_have_results(tmp_path):
    assert Ledger.load(tmp_path / "ledger.json").summary() == "No experiments have been graded yet."
