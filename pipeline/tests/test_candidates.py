"""A candidate feature cannot ship itself, and cannot cheat to look good."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nfl_pipeline.predict.analyze import analyze_week
from nfl_pipeline.predict.candidates import Candidate, evaluate
from nfl_pipeline.predict.models import PredictionModel


def frame(rows: int = 400, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    form = rng.gamma(4.0, 2.5, rows)
    return pd.DataFrame(
        {
            "player_id": [f"C{i:03d}" for i in range(rows)],
            "season": 2025,
            "week": 5,
            "position_group": ["QB", "RB", "WR", "TE", "K"] * (rows // 5),
            "prior_games": 10,
            "ppr_mean5": form,
            "ppr_mean10": form,
            "ppr_season_avg": form,
            "actual_ppr": np.maximum(form + rng.normal(0, 5, rows), 0),
            "snap_share_mean5": rng.random(rows),
        }
    )


def adds_a_harmless_column(name: str = "doubled_snaps"):
    return Candidate(
        name="harmless",
        hypothesis="snap share, doubled, means nothing but is legal",
        adds=(name,),
        build=lambda f: f.assign(**{name: f.snap_share_mean5 * 2}),
    )


def test_a_candidate_that_reads_the_outcome_is_refused():
    """The clearest way to look brilliant is to peek at the answer, so this is checked first."""
    cheat = Candidate(
        name="cheat",
        hypothesis="what if we simply knew the score",
        adds=("leak",),
        build=lambda f: f.assign(leak=f.actual_ppr * 0.9),
    )

    with pytest.raises(ValueError, match="reading the answer"):
        evaluate(cheat, frame())


def test_a_candidate_that_drops_rows_is_refused():
    """Champion and challenger must be scored on identical player-weeks."""
    shrinking = Candidate(
        name="shrinking",
        hypothesis="quietly keep only the easy players",
        adds=("x",),
        build=lambda f: f[f.ppr_mean5 > 5].assign(x=1.0),
    )

    with pytest.raises(ValueError, match="number of rows"):
        shrinking.apply(frame())


def test_a_candidate_that_reorders_rows_is_refused():
    shuffling = Candidate(
        name="shuffling",
        hypothesis="sorting cannot possibly matter",
        adds=("x",),
        build=lambda f: f.sort_values("ppr_mean5").assign(x=1.0),
    )

    with pytest.raises(ValueError, match="reordered"):
        shuffling.apply(frame())


def test_a_candidate_that_redefines_an_existing_feature_is_refused():
    """Adding a column is a proposal; silently changing one is a different model."""
    overwriting = Candidate(
        name="overwriting",
        hypothesis="ppr_mean5 would be better if it were bigger",
        adds=("ppr_mean5",),
        build=lambda f: f.assign(ppr_mean5=f.ppr_mean5 * 2),
    )

    with pytest.raises(ValueError, match="overwrite"):
        overwriting.apply(frame())


def test_a_candidate_that_does_not_add_what_it_promised_is_refused():
    forgetful = Candidate(
        name="forgetful",
        hypothesis="said it would add a column",
        adds=("never_added",),
        build=lambda f: f,
    )

    with pytest.raises(ValueError, match="promised"):
        forgetful.apply(frame())


def test_a_legal_candidate_passes_the_checks():
    out = adds_a_harmless_column().apply(frame())

    assert "doubled_snaps" in out.columns
    assert len(out) == 400


def test_the_extra_columns_do_not_leak_into_other_models():
    """A candidate under evaluation must not change what the champion trains on."""
    challenger = PredictionModel(extra_columns=("doubled_snaps",))
    champion = PredictionModel()

    assert "doubled_snaps" in challenger.columns()
    assert "doubled_snaps" not in champion.columns()


# ---------------------------------------------------------------- the failure report


def graded_frame() -> pd.DataFrame:
    f = frame(rows=200, seed=9)
    rng = np.random.default_rng(1)
    f["points"] = f.ppr_mean5 + rng.normal(0, 1, len(f))
    return f


def test_the_report_counts_only_players_who_played():
    f = graded_frame()
    f.loc[f.index[:20], "actual_ppr"] = np.nan

    report = analyze_week(f)

    assert report.player_games == 180


def test_the_report_shows_the_margin_per_position():
    report = analyze_week(graded_frame())

    assert set(report.by_position.position_group) == {"QB", "RB", "WR", "TE", "K"}
    assert "margin" in report.by_position.columns


def test_the_report_names_the_biggest_misses_with_real_names_when_it_has_them():
    f = graded_frame()
    names = pd.DataFrame({"player_id": f.player_id, "display_name": "Known Player"})

    report = analyze_week(f, names=names)

    assert (report.worst.player == "Known Player").all()
    assert len(report.worst) == 10


def test_the_report_warns_that_single_misses_are_noise():
    """A list of big misses invites story-telling, so the report says so where it is read."""
    text = analyze_week(graded_frame()).to_markdown()

    assert "mostly noise" in text
    assert "computable before kickoff" in text


def test_the_report_states_the_bar_and_the_already_rejected_ideas():
    text = analyze_week(graded_frame()).to_markdown()

    assert "0.05 mean absolute error" in text
    assert "do not propose those again" in text


def test_a_week_with_nothing_graded_is_an_error_not_an_empty_report():
    f = graded_frame()
    f["actual_ppr"] = np.nan

    with pytest.raises(ValueError, match="no graded rows"):
        analyze_week(f)
