-- One row per player per game with snap counts. Keyed by the Pro Football Reference player id,
-- which fct_player_week maps to the nflverse (gsis) player id.
with raw as (
    select * from {{ latest_raw('snap_counts') }}
),

team_map as (
    select raw_code, team_code from {{ ref('team_map') }}
)

select
    raw.game_id,
    raw.season,
    raw.week,
    raw.game_type,
    raw.pfr_player_id,
    raw.player as player_name,
    raw.position as position_raw,
    {{ std_team('raw.team', 'team_map') }} as team,
    raw.offense_snaps,
    raw.offense_pct,
    raw.defense_snaps,
    raw.defense_pct,
    raw.st_snaps,
    raw.st_pct
from raw
left join team_map on raw.team = team_map.raw_code
where raw.pfr_player_id is not null
