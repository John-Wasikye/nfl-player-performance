"""The candidates that have been proposed, as code.

Every entry here is a hypothesis someone could be wrong about, written so the harness can settle it.
A candidate stays in this file after it is rejected: the code is the record of what was tried, and
deleting it would invite proposing the same thing again next month.

Adding one is the whole of Claude's job in the weekly loop. Read the failure report, write a
function, register it here, run it. The gate decides.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nfl_pipeline.predict.candidates import Candidate


def _form_versus_baseline(features: pd.DataFrame) -> pd.DataFrame:
    """How a player's last three games compare with his own season, as a ratio.

    The model already sees both numbers. The hypothesis is that it does not easily see the
    *relationship* between them: gradient boosting splits on thresholds, so "scoring 1.4 times his
    own average" is awkward to express, while "scoring 14 points" is trivial. A ratio states it
    directly and is the kind of derived feature that has worked in published LLM feature
    engineering.

    Guarded against a zero denominator, which is common: plenty of players have a season average of
    zero, and dividing by it would hand the model an infinity to split on.
    """
    baseline = features.ppr_season_avg.fillna(features.ppr_mean10)
    recent = features.ppr_mean3.fillna(features.ppr_mean5)
    ratio = np.where(baseline > 0.5, recent / baseline.where(baseline > 0.5), np.nan)
    return features.assign(form_versus_baseline=ratio)


FORM_VERSUS_BASELINE = Candidate(
    name="form_versus_baseline",
    hypothesis=(
        "The model sees recent form and season average as separate numbers but cannot easily "
        "express their ratio, because trees split on thresholds. Stating 'hot or cold relative to "
        "himself' directly should help more than either number alone."
    ),
    adds=("form_versus_baseline",),
    build=_form_versus_baseline,
)


REGISTRY: dict[str, Candidate] = {
    FORM_VERSUS_BASELINE.name: FORM_VERSUS_BASELINE,
}
