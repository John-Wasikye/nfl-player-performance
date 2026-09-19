"""Who is going to play.

Measured on 2021-2025 (research paper section 5.10): players listed Out played 0.1% of the time and
Doubtful 0.4%, so both are treated as unavailable. Questionable is the genuinely uncertain case -
they played 63% of the time overall but only 35% at quarterback - so those players get a calibrated
probability rather than a guess.

Getting this wrong is expensive: a player who does not play scores nothing, so a wrong call costs
their whole projection (about 8 points) rather than the usual 5.4-point error.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

# Statuses that effectively rule a player out. The measured play rates are in the docstring above.
RULED_OUT = ("Out", "Doubtful")

PRACTICE_FEATURES = ("did_not_practice", "limited_practice", "full_practice")


@dataclass
class AvailabilityResult:
    """Whether a player is expected to play, and how confident we are."""

    available: pd.Series  # False for anyone ruled out entirely
    probability: pd.Series  # chance of playing, 1.0 when not on the injury report


def practice_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Turn the practice-participation text into the three flags the model uses."""
    practice = frame.get("practice_status", pd.Series([None] * len(frame), index=frame.index))
    practice = practice.fillna("")
    return pd.DataFrame(
        {
            "did_not_practice": practice.str.contains("Did Not", case=False).astype(float),
            "limited_practice": practice.str.contains("Limited", case=False).astype(float),
            "full_practice": practice.str.contains("Full", case=False).astype(float),
        },
        index=frame.index,
    )


class AvailabilityModel:
    """Predicts whether a Questionable player will play.

    Everyone not on the injury report is assumed available; anyone Out or Doubtful is not. Only the
    Questionable group is modelled, because that is the only group where the answer is in doubt.
    """

    def __init__(self) -> None:
        self._model: LogisticRegression | None = None
        self._base_rate: float = 0.63  # measured 2021-2025, used until the model is fitted
        self._columns: list[str] = []

    @staticmethod
    def _design(frame: pd.DataFrame) -> pd.DataFrame:
        x = practice_features(frame)
        x["position_code"] = frame.position_code.astype(float)
        return x

    def fit(self, questionable: pd.DataFrame, played: pd.Series) -> AvailabilityModel:
        """Fit on past Questionable player-weeks and whether each one actually played."""
        if len(questionable) < 50 or played.nunique() < 2:
            # Not enough history to model; the base rate is a better answer than a bad fit.
            self._model = None
            if len(played):
                self._base_rate = float(played.mean())
            return self
        x = self._design(questionable)
        self._columns = list(x.columns)
        self._model = LogisticRegression(max_iter=1000).fit(x, played)
        self._base_rate = float(played.mean())
        return self

    def probability_of_playing(self, frame: pd.DataFrame) -> pd.Series:
        """Chance each player takes the field. 1.0 if not listed, 0.0 if ruled out."""
        status = frame.get("injury_status", pd.Series([None] * len(frame), index=frame.index))
        probability = pd.Series(1.0, index=frame.index)
        probability[status.isin(RULED_OUT)] = 0.0

        questionable = status == "Questionable"
        if not questionable.any():
            return probability
        if self._model is None:
            probability[questionable] = self._base_rate
            return probability
        x = self._design(frame[questionable]).reindex(columns=self._columns, fill_value=0.0)
        probability[questionable] = self._model.predict_proba(x)[:, 1]
        return probability

    def evaluate(self, frame: pd.DataFrame) -> AvailabilityResult:
        probability = self.probability_of_playing(frame)
        status = frame.get("injury_status", pd.Series([None] * len(frame), index=frame.index))
        return AvailabilityResult(available=~status.isin(RULED_OUT), probability=probability)


def expected_points(points_if_playing: np.ndarray, probability: np.ndarray) -> np.ndarray:
    """Projection for someone who might not play: their score if they do, times the chance they do.

    Shown alongside the conditional figure rather than replacing it, because "12 points if he
    plays, 65% chance he plays" is more useful to a reader than a bare 7.8.
    """
    return np.asarray(points_if_playing, dtype=float) * np.asarray(probability, dtype=float)
