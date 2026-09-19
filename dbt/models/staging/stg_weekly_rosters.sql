-- Who was actually on each team's roster in each week, and in what capacity.
--
-- This is the authority on whether a player exists for a given week. The alternative — inferring a
-- roster from who has recently appeared in a box score — quietly keeps retired players on the
-- books, because "has not played lately" and "is not on the team" look identical in stats data.
--
-- `status` is nflverse's own code. The ones that matter here:
--   ACT  active roster, can play
--   DEV  practice squad; can be elevated but normally does not play
--   RES  reserve, including injured reserve
--   RET  retired
--   CUT / INA / EXE  released, inactive, or exempt
with raw as (
    select * from {{ latest_raw('weekly_rosters') }}
),

team_map as (
    select raw_code, team_code from {{ ref('team_map') }}
)

select
    raw.gsis_id as player_id,
    raw.season,
    raw.week,
    {{ std_team('raw.team', 'team_map') }} as team,
    raw.position as position_raw,
    raw.status,
    raw.status = 'ACT' as is_active,
    raw.full_name as display_name,
    raw.game_type
from raw
left join team_map on raw.team = team_map.raw_code
where raw.gsis_id is not null
