-- The leakage guard, checked in SQL.
--
-- If any backward-looking window in feat_player_week accidentally included the current row, then a
-- player's very first game would already have a value for it. Before a player's first game there is
-- nothing to average, so every trailing measure must be null and prior_games must be zero.
--
-- This catches the single most damaging mistake this project could make: a model that looks accurate
-- because it was quietly shown the answer.
select
    player_id,
    season,
    week,
    prior_games,
    ppr_mean3,
    ppr_mean5,
    ppr_mean10,
    ppr_season_avg,
    targets_mean5,
    snap_share_mean5
from {{ ref('feat_player_week') }}
where prior_games = 0
  and (
      ppr_mean3 is not null
      or ppr_mean5 is not null
      or ppr_mean10 is not null
      or ppr_season_avg is not null
      or targets_mean5 is not null
      or carries_mean5 is not null
      or attempts_mean5 is not null
      or snap_share_mean5 is not null
      or separation_mean8 is not null
  )
