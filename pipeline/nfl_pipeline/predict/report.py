"""The Report card: how the published predictions actually did.

The verdict sentence is generated from the graded numbers and nothing else. There is no branch that
can produce an encouraging line when the numbers are poor, because the whole reason this page exists
is that a prediction site with no public accuracy record is asking to be taken on faith.

Two rules the wording follows, both from section 5.15 of the research paper:

  - accuracy is always reported next to its player count, since mean absolute error depends on which
    players are included and is not comparable across different populations
  - the model is only ever compared with baselines scored on the identical rows
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from nfl_pipeline.contract import SCHEMA_VERSION, AccuracyFile, GradedWeek

# Below this many graded weeks, any apparent trend is noise. Measured in section 5.11: week-to-week
# swings are large enough that a handful of weeks can point either way by luck alone.
MIN_WEEKS_FOR_A_TREND = 4


def combine(weeks: list[GradedWeek]) -> GradedWeek | None:
    """Pool every graded week into one season-to-date line.

    Weighted by player-games, not averaged over weeks, so a quiet week counts for less than a busy
    one instead of the same.
    """
    if not weeks:
        return None
    counts = np.array([w.player_games for w in weeks], dtype=float)

    def pooled(values: list[float]) -> float:
        return round(float(np.average(np.array(values, dtype=float), weights=counts)), 4)

    names = sorted({name for w in weeks for name in w.baseline_mae})
    frozen = [w.frozen_model_mae for w in weeks]
    return GradedWeek(
        season=weeks[0].season,
        week=max(w.week for w in weeks),
        player_games=int(counts.sum()),
        mae=pooled([w.mae for w in weeks]),
        # Root mean square error pools through the squares, not the values.
        rmse=round(
            float(np.sqrt(np.average(np.array([w.rmse for w in weeks]) ** 2, weights=counts))), 4
        ),
        interval_coverage=pooled([w.interval_coverage for w in weeks]),
        baseline_mae={
            name: pooled([w.baseline_mae.get(name, np.nan) for w in weeks]) for name in names
        },
        frozen_model_mae=pooled(frozen) if all(f is not None for f in frozen) else None,
    )


def verdict(weeks: list[GradedWeek], season_to_date: GradedWeek | None) -> str:
    """One paragraph a reader can check against the tables underneath it."""
    if season_to_date is None or not weeks:
        return "No games have been graded yet this season, so there is nothing to report."

    best = min(season_to_date.baseline_mae, key=season_to_date.baseline_mae.get)
    margin = season_to_date.baseline_mae[best] - season_to_date.mae
    readable = best.replace("_", " ")
    parts = [
        f"Across {len(weeks)} graded weeks and {season_to_date.player_games:,} player-games, "
        f"projections were off by {season_to_date.mae:.2f} fantasy points on average."
    ]

    if margin <= 0:
        parts.append(
            f"That is worse than simply using each player's {readable} "
            f"({season_to_date.baseline_mae[best]:.2f}), so the model is not currently earning its "
            "place."
        )
    elif margin < 0.15:
        parts.append(
            f"A player's {readable} would have been off by {season_to_date.baseline_mae[best]:.2f}, "
            f"so the model is ahead by only {margin:.2f} points, which is inside the margin this "
            "project treats as noise."
        )
    else:
        parts.append(
            f"A player's {readable} would have been off by {season_to_date.baseline_mae[best]:.2f}, "
            f"so the model is ahead by {margin:.2f} points per game."
        )

    coverage = season_to_date.interval_coverage
    if 0.78 <= coverage <= 0.82:
        parts.append(f"The 80% ranges contained the real result {coverage:.0%} of the time.")
    else:
        direction = "too narrow" if coverage < 0.78 else "wider than they need to be"
        parts.append(
            f"The 80% ranges contained the real result {coverage:.0%} of the time, so they are "
            f"currently {direction}."
        )

    parts.append(_learning_sentence(weeks, season_to_date))
    return " ".join(p for p in parts if p)


def _learning_sentence(weeks: list[GradedWeek], season_to_date: GradedWeek) -> str:
    """Whether "it is getting better" is true, answered against the frozen control.

    Section 5.11 found that weekly retraining is worth about 0.7% and that the gap does not widen as
    a season goes on. So the honest default is to report no detectable improvement, and only claim
    otherwise when the control line says so.
    """
    if season_to_date.frozen_model_mae is None:
        return (
            "The frozen-model control has not been graded yet, so there is no basis yet for saying "
            "whether the system is improving."
        )
    gain = season_to_date.frozen_model_mae - season_to_date.mae
    if len(weeks) < MIN_WEEKS_FOR_A_TREND:
        return (
            f"Against a model frozen before the season the difference is {gain:+.2f} points, but "
            f"{len(weeks)} weeks is too few to read anything into."
        )
    if gain > 0.05:
        return (
            f"It is beating a model frozen before the season by {gain:.2f} points per game, which "
            "is what 'improving' means here."
        )
    if gain < -0.05:
        return (
            f"It is currently {-gain:.2f} points per game worse than a model frozen before the "
            "season, so this year's changes have not helped."
        )
    return (
        "It is level with a model frozen before the season, so nothing added this year has made a "
        "measurable difference yet."
    )


def build_accuracy_file(season: int, weeks: list[GradedWeek]) -> AccuracyFile:
    ordered = sorted(weeks, key=lambda w: w.week)
    season_to_date = combine(ordered)
    return AccuracyFile(
        schema_version=SCHEMA_VERSION,
        season=season,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        weeks=ordered,
        season_to_date=season_to_date,
        verdict=verdict(ordered, season_to_date),
    )
