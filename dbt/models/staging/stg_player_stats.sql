-- One row per player per week (all season types), straight from nflverse's weekly player stats.
-- Teams and positions are standardized; headshot URLs and the free-text fg distance lists are dropped.
-- Rows without a player id (a couple of unattributed lines each week) are excluded.
with raw as (
    select * from {{ latest_raw('stats_player') }}
),

team_map as (
    select raw_code, team_code from {{ ref('team_map') }}
),

position_map as (
    select position, position_group from {{ ref('position_map') }}
)

select
    raw.* exclude (
        headshot_url,
        position,
        position_group,
        team,
        opponent_team,
        fg_made_list,
        fg_missed_list,
        fg_blocked_list,
        gwfg_distance
    ),
    raw.position as position_raw,
    position_map.position_group,
    {{ std_team('raw.team', 'team_map') }} as team,
    {{ std_team('raw.opponent_team', 'opp_map') }} as opponent_team
from raw
left join team_map on raw.team = team_map.raw_code
left join team_map as opp_map on raw.opponent_team = opp_map.raw_code
left join position_map on raw.position = position_map.position
where raw.player_id is not null
