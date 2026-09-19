"""I. Availability: the prediction problem where words, not numbers, carry the information.

H showed point-prediction accuracy is close to its ceiling. This tests a different and much less
saturated problem: will a player listed Questionable actually play, and what does getting it wrong
cost? Availability is decided by injury-report language and practice patterns, so it is the natural
place for a layer that reads text rather than numbers.

  1  How costly is an availability mistake compared with a normal prediction error?
  2  How well can structured fields alone predict it (a ceiling for the numbers-only approach)?
  3  How much signal is left in the injury *description* itself, which the model never sees?
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from common import connect, save
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

warnings.filterwarnings("ignore")


def load(con) -> pd.DataFrame:
    inj = con.sql(
        """
        select i.player_id, i.season, i.week, i.report_status, i.practice_status,
               i.report_primary_injury as injury, d.position_group as pos
        from stg_injuries i join dim_player d using (player_id)
        where i.season between 2021 and 2025
          and d.position_group in ('QB','RB','WR','TE','K')
          and i.report_status is not null
        """
    ).df()
    played = con.sql(
        """
        select f.player_id, f.season, f.week, 1 as played, p.fantasy_points_scored as pts
        from fct_player_week f join int_weekly_fantasy_points p using (player_id, season, week)
        where f.season_type = 'REG' and f.season between 2021 and 2025
        """
    ).df()
    df = inj.merge(played, on=["player_id", "season", "week"], how="left")
    df["played"] = df.played.fillna(0).astype(int)
    df["pts"] = df.pts.fillna(0.0)
    return df.sort_values(["player_id", "season", "week"])


def main() -> None:
    con = connect()
    df = load(con)
    q = df[df.report_status == "Questionable"].copy()

    # --- 1. what does an availability mistake cost?
    # If we predict a Questionable player as if he plays and he does not, the error is his whole
    # projected score. Compare that with the typical error on a player who does play.
    typical = q[q.played == 1].pts
    cost_of_missing = float(typical.mean())
    result = {
        "questionable_player_weeks": int(len(q)),
        "base_rate_plays": float(q.played.mean()),
        "mean_points_when_they_play": cost_of_missing,
        "note": "A wrong availability call costs roughly the player's whole score; the model's "
        "typical error on a player who plays is about 5.4 points.",
    }

    # --- 2. how far do the structured fields get us?
    q["dnp"] = (q.practice_status == "Did Not Participate In Practice").astype(int)
    q["limited"] = (q.practice_status == "Limited Participation in Practice").astype(int)
    q["full"] = (q.practice_status == "Full Participation in Practice").astype(int)
    hist = q.groupby("player_id").played.transform(lambda s: s.shift(1).expanding().mean())
    q["player_history"] = hist.fillna(q.played.mean())
    for pos in ("QB", "RB", "WR", "TE", "K"):
        q[f"pos_{pos}"] = (q.pos == pos).astype(int)

    feats = ["dnp", "limited", "full", "player_history"] + [
        f"pos_{p}" for p in ("QB", "RB", "WR", "TE", "K")
    ]
    train, test = q[q.season <= 2023], q[q.season >= 2024]
    model = LogisticRegression(max_iter=1000).fit(train[feats], train.played)
    prob = model.predict_proba(test[feats])[:, 1]
    base = np.full(len(test), train.played.mean())
    result["structured_model"] = {
        "test_rows": int(len(test)),
        "auc": float(roc_auc_score(test.played, prob)),
        "brier": float(brier_score_loss(test.played, prob)),
        "brier_of_base_rate": float(brier_score_loss(test.played, base)),
        "accuracy_at_50pct": float(((prob > 0.5).astype(int) == test.played).mean()),
        "accuracy_of_always_predicting_plays": float(test.played.mean()),
    }

    # --- 3. how much does the injury description itself matter?
    # The body part is recorded as free text and is never given to the model. If play rates differ
    # sharply by injury type, that is signal a text-reading layer could supply.
    by_injury = (
        q.groupby(q.injury.fillna("(blank)").str.strip().str.title())
        .agg(weeks=("played", "size"), plays=("played", "mean"))
        .query("weeks >= 40")
        .sort_values("plays")
    )
    result["play_rate_by_injury_type"] = by_injury.round(3).reset_index().to_dict("records")
    result["spread_across_injury_types"] = {
        "lowest": float(by_injury.plays.min()),
        "highest": float(by_injury.plays.max()),
        "range": float(by_injury.plays.max() - by_injury.plays.min()),
        "types_considered": int(len(by_injury)),
    }

    # Does adding the injury type to the structured model help? (one-hot, common types only)
    common = by_injury.index.tolist()
    q["injury_clean"] = q.injury.fillna("(blank)").str.strip().str.title()
    for name in common:
        q[f"inj_{name}"] = (q.injury_clean == name).astype(int)
    feats2 = feats + [f"inj_{n}" for n in common]
    train2, test2 = q[q.season <= 2023], q[q.season >= 2024]
    model2 = LogisticRegression(max_iter=2000).fit(train2[feats2], train2.played)
    prob2 = model2.predict_proba(test2[feats2])[:, 1]
    result["structured_plus_injury_type"] = {
        "auc": float(roc_auc_score(test2.played, prob2)),
        "brier": float(brier_score_loss(test2.played, prob2)),
        "auc_gain_from_injury_text": float(
            roc_auc_score(test2.played, prob2) - roc_auc_score(test.played, prob)
        ),
    }
    save("i_availability", result)

    print(f"Questionable player-weeks: {len(q)}, base rate plays {q.played.mean():.1%}")
    print(f"mean points when they do play: {cost_of_missing:.1f}  (model's typical error ~5.4)\n")
    s = result["structured_model"]
    print(
        f"structured fields only:   AUC {s['auc']:.3f}  Brier {s['brier']:.4f} "
        f"(base rate {s['brier_of_base_rate']:.4f})"
    )
    s2 = result["structured_plus_injury_type"]
    print(
        f"+ injury type from text:  AUC {s2['auc']:.3f}  Brier {s2['brier']:.4f}  "
        f"AUC gain {s2['auc_gain_from_injury_text']:+.3f}\n"
    )
    sp = result["spread_across_injury_types"]
    print(
        f"play rate ranges from {sp['lowest']:.0%} to {sp['highest']:.0%} across "
        f"{sp['types_considered']} injury types (range {sp['range']:.0%})"
    )
    print("\nleast likely to play:")
    for r in result["play_rate_by_injury_type"][:5]:
        print(f"  {r['injury']:20s} {r['plays']:.0%}  ({r['weeks']} weeks)")
    print("most likely to play:")
    for r in result["play_rate_by_injury_type"][-5:]:
        print(f"  {r['injury']:20s} {r['plays']:.0%}  ({r['weeks']} weeks)")


if __name__ == "__main__":
    main()
