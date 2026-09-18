{{ config(severity='warn') }}

-- Weekly stats should only exist for games that are final in the schedule. This is a warning, not an
-- error, because nflverse's stats and schedule files refresh at different times of day.
select
    fct.game_id,
    fct.season,
    fct.week,
    count(*) as stat_lines
from {{ ref('fct_player_week') }} as fct
inner join {{ ref('dim_game') }} as game on fct.game_id = game.game_id
where not game.is_final
group by all
