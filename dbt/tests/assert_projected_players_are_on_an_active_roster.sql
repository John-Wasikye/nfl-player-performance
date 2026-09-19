-- Every player carried for an unplayed week must be on that week's active roster.
--
-- This exists because of a real failure. The upcoming week's players were once inferred from who
-- had recently appeared in a box score, which projected Philip Rivers, retired, for 2026. Stats
-- data cannot tell "has not played lately" from "is not on the team"; only the roster can.
--
-- Rows with an outcome are exempt: a player who actually played that week is on the roster by
-- definition, and historical roster files can disagree with the box score at the margins.
select
    feat.player_id,
    feat.season,
    feat.week,
    feat.team
from {{ ref('feat_player_week') }} as feat
left join {{ ref('stg_weekly_rosters') }} as roster
    on roster.player_id = feat.player_id
    and roster.season = feat.season
    and roster.week = feat.week
    and roster.is_active
where feat.actual_ppr is null
  and roster.player_id is null
