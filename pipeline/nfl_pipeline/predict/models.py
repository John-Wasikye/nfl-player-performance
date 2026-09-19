"""The prediction model: a point estimate and an honest range.

Deliberately simple, because the research measured how little room there is. A regularized linear
model reached 0.280 R-squared and gradient boosting 0.288, against 0.232 for a plain recent average;
averaging the two gave 0.289. Nothing more elaborate is justified by the data, so the ensemble is
those two plus the recent average as a floor.

Ranges come from quantile models corrected by split conformal prediction. Raw quantiles covered only
77% of outcomes for a nominal 80% interval; the correction brought that to 79.7%.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nfl_pipeline.predict.features import model_columns

LOW_QUANTILE = 0.1
HIGH_QUANTILE = 0.9
NOMINAL_COVERAGE = HIGH_QUANTILE - LOW_QUANTILE

GBM_PARAMS = dict(
    objective="regression",
    learning_rate=0.03,
    num_leaves=15,
    min_data_in_leaf=60,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbose=-1,
    seed=7,
)
BOOSTING_ROUNDS = 400
MIN_TRAINING_ROWS = 400
# A player needs some history before a projection means anything.
MIN_PRIOR_GAMES = 3
# A player needs a real role before a *model* is worth more than his own recent average. Research
# section 5.15 measured the model losing to a plain average below this line (-0.291 mean absolute
# error for players under 2 points, -0.093 from 2 to 4) and winning above it, rising steadily to
# +0.292 for players averaging 13 or more. 4.0 is the smallest cut-off that clears the 0.15
# promotion bar, chosen over higher ones to keep as many players on the site as possible.
MIN_RECENT_SCORING = 4.0


@dataclass
class Prediction:
    """One player's projection for one game."""

    player_id: str
    season: int
    week: int
    position_group: str
    points: float
    low: float
    high: float
    probability_of_playing: float
    expected_points: float
    model_version: str


@dataclass
class PredictionModel:
    """Trains on past player-weeks and projects the next ones.

    `conformal_offset` widens the raw quantile range by however much it was found to be too narrow
    on data the quantile models never saw.
    """

    version: str = "v1"
    conformal_offset: float = 0.0
    # Extra feature columns a candidate wants tried, on top of the standard set. Held per instance
    # rather than appended to the module-level list, so a candidate under evaluation cannot leak
    # into the champion or into anything else running in the same process.
    extra_columns: tuple[str, ...] = ()
    _gbm: lgb.Booster | None = field(default=None, repr=False)
    _ridge: object | None = field(default=None, repr=False)
    _low: lgb.Booster | None = field(default=None, repr=False)
    _high: lgb.Booster | None = field(default=None, repr=False)
    _medians: pd.Series | None = field(default=None, repr=False)

    # ---------------------------------------------------------------- fitting

    def columns(self) -> list[str]:
        """Everything this model trains on: the standard features plus any candidate extras."""
        return [*model_columns(), *self.extra_columns]

    @staticmethod
    def trainable(frame: pd.DataFrame) -> pd.DataFrame:
        """Rows worth learning from: enough history, and the player actually played."""
        return frame[(frame.prior_games >= MIN_PRIOR_GAMES) & frame.actual_ppr.notna()]

    @staticmethod
    def predictable(frame: pd.DataFrame) -> pd.DataFrame:
        """Rows worth projecting: enough history, and no requirement to have played yet.

        Separate from `trainable` because the whole point of a live projection is that the outcome
        does not exist. Using `trainable` here would silently return an empty frame for any week
        that has not been played, which is every week we actually care about.
        """
        return frame[frame.prior_games >= MIN_PRIOR_GAMES]

    @staticmethod
    def eligible(frame: pd.DataFrame) -> pd.DataFrame:
        """Players with a real enough role that a model beats their own recent average.

        Note that this narrows *publishing*, not *training*. Experiment K found the model learns
        slightly better from the full population (margin +0.170 against +0.159) and there is no
        reason to throw away data. What the low-volume players must not do is set the width of the
        published ranges: see `_calibrate`.
        """
        return frame[frame.ppr_mean5.fillna(0) >= MIN_RECENT_SCORING]

    def fit(
        self, history: pd.DataFrame, calibration: pd.DataFrame | None = None
    ) -> PredictionModel:
        """Fit on `history`; if `calibration` is given, use it to correct the range width.

        The calibration set must be data the quantile models were not fitted on, otherwise the
        correction is measured against predictions that have already seen the answer.
        """
        if calibration is not None:
            self._reject_overlap(history, calibration)
        train = self.trainable(history)
        if len(train) < MIN_TRAINING_ROWS:
            raise ValueError(f"need at least {MIN_TRAINING_ROWS} rows to fit, got {len(train)}")

        columns = self.columns()
        x = train[columns].astype(float)
        self._medians = x.median()
        x = x.fillna(self._medians)
        y = train.actual_ppr

        self._gbm = lgb.train(GBM_PARAMS, lgb.Dataset(x, y), num_boost_round=BOOSTING_ROUNDS)
        self._ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 20))).fit(
            x, y
        )
        self._low = lgb.train(
            {**GBM_PARAMS, "objective": "quantile", "alpha": LOW_QUANTILE},
            lgb.Dataset(x, y),
            num_boost_round=BOOSTING_ROUNDS,
        )
        self._high = lgb.train(
            {**GBM_PARAMS, "objective": "quantile", "alpha": HIGH_QUANTILE},
            lgb.Dataset(x, y),
            num_boost_round=BOOSTING_ROUNDS,
        )
        self.conformal_offset = self._calibrate(calibration) if calibration is not None else 0.0
        return self

    @staticmethod
    def _reject_overlap(history: pd.DataFrame, calibration: pd.DataFrame) -> None:
        """Refuse to calibrate on rows the model was fitted on.

        Conformal calibration measures how often outcomes fall outside the predicted range. If the
        quantile models have already seen those outcomes the range looks better than it is, and the
        published interval would be too narrow. This is easy to do by accident, so it is an error
        rather than a warning.
        """
        key = ["player_id", "season", "week"]
        overlap = calibration.merge(history[key].drop_duplicates(), on=key, how="inner")
        if len(overlap):
            raise ValueError(
                f"{len(overlap)} calibration rows were also used for training; "
                "calibrate on a period the model has not seen"
            )

    def _calibrate(self, calibration: pd.DataFrame) -> float:
        """How much too narrow is the raw range? Split-conformal, on unseen *publishable* data.

        The eligibility filter here is not a detail. Conformal prediction only guarantees coverage
        when the calibration set is exchangeable with what is being predicted. Calibrating on a
        population full of low-volume players — whose errors are small, because near-zero scores are
        easy — produces an offset that is too narrow for the players actually published. Experiment
        K measured exactly that: training on everyone and calibrating on everyone dropped coverage
        from 0.798 to 0.778, against a nominal 0.80.

        So the model trains on all the data it can and calibrates on the population it will be
        judged against.
        """
        usable = self.eligible(self.trainable(calibration))
        if len(usable) < 100:
            return 0.0
        x = self._prepare(usable)
        low, high = self._low.predict(x), self._high.predict(x)
        actual = usable.actual_ppr.to_numpy()
        # How far outside the range each outcome fell (negative when comfortably inside).
        miss = np.maximum(low - actual, actual - high)
        return float(np.quantile(miss, min(0.999, NOMINAL_COVERAGE * (1 + 1 / len(miss)))))

    # ---------------------------------------------------------------- predicting

    def _prepare(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame[self.columns()].astype(float).fillna(self._medians)

    def predict_points(self, frame: pd.DataFrame) -> np.ndarray:
        """The ensemble's point estimate, floored at zero."""
        if self._gbm is None:
            raise ValueError("the model has not been fitted")
        x = self._prepare(frame)
        blended = 0.5 * self._gbm.predict(x) + 0.5 * self._ridge.predict(x)
        return np.maximum(blended, 0.0)

    def predict_interval(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """The 80% range, widened by the conformal correction and floored at zero."""
        x = self._prepare(frame)
        low = self._low.predict(x) - self.conformal_offset
        high = self._high.predict(x) + self.conformal_offset
        # Quantile models are fitted separately and can cross on odd rows; order them.
        low, high = np.minimum(low, high), np.maximum(low, high)
        return np.maximum(low, 0.0), np.maximum(high, 0.0)

    def predict(
        self, frame: pd.DataFrame, play_probability: np.ndarray | None = None
    ) -> pd.DataFrame:
        """Point estimate, range, and the availability-adjusted expectation, as a frame."""
        points = self.predict_points(frame)
        low, high = self.predict_interval(frame)
        probability = (
            np.ones(len(frame)) if play_probability is None else np.asarray(play_probability, float)
        )
        return pd.DataFrame(
            {
                "player_id": frame.player_id.to_numpy(),
                "season": frame.season.to_numpy(),
                "week": frame.week.to_numpy(),
                "position_group": frame.position_group.to_numpy(),
                "points": points,
                "low": low,
                "high": high,
                "probability_of_playing": probability,
                "expected_points": points * probability,
                "model_version": self.version,
            },
            index=frame.index,
        )


def baseline_predictions(frame: pd.DataFrame) -> dict[str, np.ndarray]:
    """The simple methods any model has to beat before it is worth anything.

    The research found these are already close to the ceiling, so they are kept permanently as the
    control the Report card is measured against.
    """
    recent = frame.ppr_mean5.fillna(frame.ppr_mean10).fillna(frame.ppr_season_avg)
    return {
        "recent_average": recent.fillna(0.0).to_numpy(),
        "season_average": frame.ppr_season_avg.fillna(recent).fillna(0.0).to_numpy(),
        "last_ten": frame.ppr_mean10.fillna(recent).fillna(0.0).to_numpy(),
    }
