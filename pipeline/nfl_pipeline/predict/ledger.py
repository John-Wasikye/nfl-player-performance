"""The experiment ledger: every change that was tried, and what the gate decided.

Published in full, including the failures. That is the point of it. A page showing only the changes
that worked would suggest a system that improves whenever it is touched, when the truth measured in
this project is the opposite: most ideas that sound good lose to a simple average, and the value is
in having a referee that says so cheaply.

The ledger is append-only for the same reason the weekly predictions are locked. A record of what
was decided is worth nothing if a later run can rewrite it once the outcome is known.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nfl_pipeline.contract import LedgerEntry

logger = logging.getLogger("nfl_pipeline.predict.ledger")


@dataclass
class Ledger:
    """Every graded experiment, oldest first."""

    path: Path
    entries: list[LedgerEntry]

    @classmethod
    def load(cls, path: Path) -> Ledger:
        path = Path(path)
        if not path.exists():
            return cls(path=path, entries=[])
        payload = json.loads(path.read_text("utf-8"))
        return cls(path=path, entries=[LedgerEntry(**row) for row in payload["entries"]])

    def record(
        self,
        entry_id: str,
        hypothesis: str,
        change: str,
        decision: dict,
        proposed_at: str | None = None,
        metric: str = "mae",
    ) -> LedgerEntry:
        """Append one decision, straight from `promotion_decision`.

        Recording the same `entry_id` twice raises. An experiment has one outcome; running it
        again makes it a new experiment with a new id, so a result cannot be quietly replaced
        by a luckier re-run of the same idea.
        """
        if any(e.entry_id == entry_id for e in self.entries):
            raise ValueError(
                f"{entry_id} is already in the ledger. Re-running an experiment makes it a new "
                "entry; an existing result is never overwritten."
            )
        entry = LedgerEntry(
            entry_id=entry_id,
            proposed_at=proposed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            hypothesis=hypothesis,
            change=change,
            champion_score=decision["champion_mae"],
            challenger_score=decision["challenger_mae"],
            improvement=decision["improvement"],
            promoted=decision["promote"],
            reason=decision["reason"],
            metric=metric,
        )
        self.entries.append(entry)
        logger.info(
            "ledger: %s %s (%s)",
            entry_id,
            "promoted" if entry.promoted else "rejected",
            entry.reason,
        )
        return entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"entries": [e.model_dump() for e in self.entries]}, indent=2),
            encoding="utf-8",
        )

    @property
    def promoted(self) -> list[LedgerEntry]:
        return [e for e in self.entries if e.promoted]

    @property
    def rejected(self) -> list[LedgerEntry]:
        return [e for e in self.entries if not e.promoted]

    def summary(self) -> str:
        """One plain sentence for the site, built only from the counts."""
        if not self.entries:
            return "No experiments have been graded yet."
        tried, kept = len(self.entries), len(self.promoted)
        if kept == 0:
            return (
                f"{tried} changes have been tested and none beat the current model. "
                "Nothing shipped, which is the system working as intended."
            )
        dropped = tried - kept
        # Deliberately no total: entries judged on different metrics cannot be added up, and a
        # tidy-looking sum of incomparable numbers is the exact mistake this ledger exists to avoid.
        tail = (
            "every one of them was kept"
            if dropped == 0
            else f"the other {'one was' if dropped == 1 else f'{dropped} were'} rejected"
        )
        return (
            f"{tried} changes tested, {kept} kept; {tail} and listed below with the numbers that "
            "decided it."
        )
