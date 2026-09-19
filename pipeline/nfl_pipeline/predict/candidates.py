"""Candidate features, and the harness that accepts or rejects them.

This is the mechanism behind the claim that the system can only get better. A candidate is a plain
function that adds columns to the feature frame. The harness runs the champion and the challenger
through the same walk-forward replay and asks the promotion gate to decide. Nothing here can ship a
change on its own.

Claude's role is to write the functions. It never scores them, never sees a decision it can argue
with, and never touches a published number — the research found that every version of "let the model
adjust itself" made predictions worse, so the only job left for judgement is proposing what to try.

Two rules keep a candidate honest, and both are enforced rather than documented:

  - it may only read columns that existed before the week in question, so a candidate cannot invent
    a feature out of the outcome it is meant to predict
  - it must not drop or reorder rows, because the harness compares champion and challenger on
    identical player-weeks and silently losing rows would flatter whichever side lost them
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from nfl_pipeline.predict.backtest import promotion_decision, walk_forward
from nfl_pipeline.predict.models import PredictionModel

logger = logging.getLogger("nfl_pipeline.predict.candidates")

# Columns a candidate must never read: they are the answer, or derived from it.
FORBIDDEN = ("actual_ppr",)

CandidateFn = Callable[[pd.DataFrame], pd.DataFrame]


@dataclass
class Candidate:
    """One proposed change: a name, why it might work, and the code that does it."""

    name: str
    hypothesis: str
    adds: tuple[str, ...]
    build: CandidateFn

    def apply(self, features: pd.DataFrame) -> pd.DataFrame:
        before = features[["player_id", "season", "week"]].reset_index(drop=True)
        out = self.build(features.copy())
        self._check(features, out, before)
        return out

    def _check(self, original: pd.DataFrame, out: pd.DataFrame, before: pd.DataFrame) -> None:
        if len(out) != len(original):
            raise ValueError(
                f"{self.name} changed the number of rows from {len(original)} to {len(out)}; "
                "a candidate may add columns but must leave the player-weeks alone"
            )
        after = out[["player_id", "season", "week"]].reset_index(drop=True)
        if not after.equals(before):
            raise ValueError(
                f"{self.name} reordered or altered the player-weeks; champion and challenger have "
                "to be compared on identical rows"
            )
        missing = [column for column in self.adds if column not in out.columns]
        if missing:
            raise ValueError(f"{self.name} promised {missing} but did not add them")
        for column in self.adds:
            if column in original.columns:
                raise ValueError(
                    f"{self.name} would overwrite the existing column {column!r}; "
                    "a candidate adds features, it does not redefine them"
                )


@dataclass
class CandidateResult:
    name: str
    hypothesis: str
    adds: tuple[str, ...]
    decision: dict
    champion: dict = field(default_factory=dict)
    challenger: dict = field(default_factory=dict)


def evaluate(
    candidate: Candidate,
    features: pd.DataFrame,
    test_seasons: tuple[int, ...] = (2024, 2025),
) -> CandidateResult:
    """Replay history with and without the candidate, then let the gate decide.

    Both runs see the same rows and the same weeks. The only difference is the extra columns, which
    is the whole point: anything else moving would make the comparison meaningless.

    Known limitation, worth fixing before this loop has decided much. The comparison is scored on
    every trainable player-week, but the site publishes only the players in `PredictionModel.
    eligible` — roughly two thirds of them. A candidate that helps exactly the players we publish
    and does nothing for the rest would therefore have its effect diluted here, and could be
    rejected for being small when it was not. The comparison is still fair, because both sides are
    scored on identical rows; it is just measured over a wider population than the one being judged
    on the Report card.
    """
    _reject_forbidden_reads(candidate, features)

    enriched = candidate.apply(features)
    champion = walk_forward(features, test_seasons=test_seasons)
    challenger = walk_forward(
        enriched,
        test_seasons=test_seasons,
        model_factory=_with_extra_columns(candidate.adds),
    )
    decision = promotion_decision(champion, challenger)
    logger.info(
        "candidate %s: %s (%s)",
        candidate.name,
        "promoted" if decision["promote"] else "rejected",
        decision["reason"],
    )
    return CandidateResult(
        name=candidate.name,
        hypothesis=candidate.hypothesis,
        adds=candidate.adds,
        decision=decision,
        champion=champion.summary(),
        challenger=challenger.summary(),
    )


def _reject_forbidden_reads(candidate: Candidate, features: pd.DataFrame) -> None:
    """Refuse a candidate that would need the answer to compute itself.

    Checked by running it on a frame whose outcome column has been blanked. A candidate that reads
    the outcome will either fail outright or produce different values, and either way it is not a
    feature — it is the label wearing a hat.
    """
    blinded = features.copy()
    for column in FORBIDDEN:
        if column in blinded.columns:
            blinded[column] = pd.NA

    honest = candidate.build(features.copy())
    try:
        blind = candidate.build(blinded)
    except Exception as error:  # noqa: BLE001 - any failure here means it read the outcome
        raise ValueError(
            f"{candidate.name} cannot be computed without {FORBIDDEN}, so it is not a feature: "
            f"{error}"
        ) from error

    for column in candidate.adds:
        if column not in honest.columns or column not in blind.columns:
            continue
        if not honest[column].equals(blind[column]):
            raise ValueError(
                f"{candidate.name} produces different values for {column!r} when the outcome is "
                "hidden, so it is reading the answer it is supposed to predict"
            )


def _with_extra_columns(adds: tuple[str, ...]):
    """A model factory that trains on the usual columns plus the candidate's."""

    def factory() -> PredictionModel:
        return PredictionModel(version="challenger", extra_columns=tuple(adds))

    return factory
