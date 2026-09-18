-- One row per player. Starts from the nflverse player database and adds any player who has a
-- weekly stat line but is missing from it, so every fact row has a matching player.
with from_database as (
    select
        player_id,
        display_name,
        birth_date,
        position_raw,
        position_group,
        rookie_season,
        last_season,
        latest_team,
        draft_year,
        pfr_id
    from {{ ref('stg_players') }}
),

seen_in_stats as (
    select
        player_id,
        arg_max(player_display_name, week) as display_name,
        arg_max(position_raw, week) as position_raw,
        arg_max(position_group, week) as position_group,
        arg_max(team, week) as latest_team
    from {{ ref('stg_player_stats') }}
    group by player_id
)

select
    player_id, display_name, birth_date, position_raw, position_group,
    rookie_season, last_season, latest_team, draft_year, pfr_id,
    false as added_from_stats
from from_database

union all

select
    s.player_id, s.display_name, null, s.position_raw, s.position_group,
    null, null, s.latest_team, null, null,
    true
from seen_in_stats as s
where s.player_id not in (select player_id from from_database)
