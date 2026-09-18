-- One row per player in the nflverse player database. Headshot URLs are deliberately dropped:
-- they point at the NFL's own image host, which the NFL's terms do not allow us to display.
with raw as (
    select * from {{ latest_raw('players') }}
),

team_map as (
    select raw_code, team_code from {{ ref('team_map') }}
),

position_map as (
    select position, position_group from {{ ref('position_map') }}
)

select
    raw.gsis_id as player_id,
    raw.display_name,
    raw.first_name,
    raw.last_name,
    try_cast(raw.birth_date as date) as birth_date,
    raw.position as position_raw,
    position_map.position_group,
    raw.height,
    raw.weight,
    raw.college_name,
    raw.rookie_season,
    raw.last_season,
    {{ std_team('raw.latest_team', 'team_map') }} as latest_team,
    raw.status,
    raw.years_of_experience,
    raw.draft_year,
    raw.draft_round,
    raw.draft_pick,
    raw.pfr_id,
    raw.espn_id,
    raw._ingest_date
from raw
left join team_map on raw.latest_team = team_map.raw_code
left join position_map on raw.position = position_map.position
where raw.gsis_id is not null
