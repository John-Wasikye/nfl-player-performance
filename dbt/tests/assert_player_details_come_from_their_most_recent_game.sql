-- For a player whose details are derived from box scores, those details must come from his most
-- recent game.
--
-- Scoped to `added_from_stats` on purpose. Players present in the nflverse players file take their
-- team from that file, which tracks the *current* roster rather than the last game played, and the
-- two legitimately differ: a quarterback who has not taken a snap this season is still on his new
-- team. Comparing those would assert something false.
--
-- That leaves the fallback branch, which is empty today, so this test currently passes vacuously.
-- It is here because the obvious way to write that branch — `arg_max(team, week)` — orders by week
-- number across every season at once and would hand a multi-season player his older details. The
-- values would all look individually plausible; only the pairing would be wrong.
with most_recent as (
    select
        player_id,
        team,
        position_group,
        player_display_name,
        row_number() over (partition by player_id order by season desc, week desc) as recency
    from {{ ref('stg_player_stats') }}
)

select
    player.player_id,
    player.latest_team,
    most_recent.team as should_be
from {{ ref('dim_player') }} as player
inner join most_recent
    on most_recent.player_id = player.player_id
    and most_recent.recency = 1
where player.added_from_stats
  and (
    player.latest_team is distinct from most_recent.team
    or player.position_group is distinct from most_recent.position_group
    or player.display_name is distinct from most_recent.player_display_name
  )
