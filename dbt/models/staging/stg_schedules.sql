-- One row per scheduled game (past and upcoming), with standardized team codes.
-- spread_line follows nflverse's convention: positive means the home team is favored.
with raw as (
    select * from {{ latest_raw('schedules') }}
),

team_map as (
    select raw_code, team_code from {{ ref('team_map') }}
)

select
    raw.game_id,
    raw.season,
    raw.game_type,
    raw.week,
    cast(raw.gameday as date) as game_date,
    raw.weekday,
    -- kickoff as a naive timestamp in US Eastern time, as published by nflverse
    try_strptime(raw.gameday || ' ' || raw.gametime, '%Y-%m-%d %H:%M') as kickoff_et,
    {{ std_team('raw.home_team', 'home_map') }} as home_team,
    {{ std_team('raw.away_team', 'away_map') }} as away_team,
    raw.home_score,
    raw.away_score,
    (raw.home_score is not null and raw.away_score is not null) as is_final,
    raw.overtime = 1 as went_to_overtime,
    raw.location,
    raw.home_rest,
    raw.away_rest,
    raw.spread_line,
    raw.total_line,
    raw.home_moneyline,
    raw.away_moneyline,
    raw.div_game = 1 as is_divisional,
    raw.roof,
    raw.surface,
    raw.temp,
    raw.wind,
    raw.stadium_id,
    raw.stadium,
    raw.home_qb_id,
    raw.away_qb_id,
    raw.home_coach,
    raw.away_coach,
    raw._ingest_date
from raw
left join team_map as home_map on raw.home_team = home_map.raw_code
left join team_map as away_map on raw.away_team = away_map.raw_code
