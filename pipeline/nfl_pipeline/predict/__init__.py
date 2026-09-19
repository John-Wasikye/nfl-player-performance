"""The weekly prediction engine.

Built on the evidence in PREDICTION_RESEARCH_PAPER.md, which measured the ceiling before any of
this was written: an oracle knowing each player's true season average scores 5.074 mean absolute
error against a working model's 5.445, so the whole remaining headroom is under 7%. The design
follows from that. Simple models, honest ranges, and no mechanism that adjusts itself without
first proving it helps.
"""

from nfl_pipeline.predict.availability import AvailabilityModel
from nfl_pipeline.predict.features import FEATURE_COLUMNS, load_features
from nfl_pipeline.predict.models import Prediction, PredictionModel

__all__ = [
    "AvailabilityModel",
    "FEATURE_COLUMNS",
    "Prediction",
    "PredictionModel",
    "load_features",
]
