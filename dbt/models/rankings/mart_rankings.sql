-- The position rankings, as a weekly snapshot: one row per player per week per position.
--
-- Two ranking views sit side by side:
--   composite_*  the 0-100 score built from efficiency and production percentiles. Only qualified
--                players (meeting the position's minimum role) get a rank; the rest are listed unranked.
--   fantasy_*    season-to-date PPR fantasy points. Everyone with a game is ranked.
-- *_rank_prev is the rank one week earlier and *_movement = previous rank - current rank, so a
-- positive movement means the player moved up. *_is_new marks a player ranked for the first time
-- after the season's first week.
with scores as (
    select * from {{ ref('int_rank_scores') }}
),

ranked as (
    select
        scores.*,
        case
            when is_qualified then row_number() over (
                partition by season, week, position_group, is_qualified
                order by composite_score desc nulls last, ppr_points desc, games desc, player_id
            )
        end as composite_rank,
        row_number() over (
            partition by season, week, position_group
            order by ppr_points desc, games desc, player_id
        ) as fantasy_rank,
        min(week) over (partition by season) as season_first_week
    from scores
),

week_status as (
    select season, week, bool_and(is_final) as week_complete
    from {{ ref('dim_game') }}
    where game_type = 'REG'
    group by all
)

select
    ranked.season,
    ranked.week,
    ranked.position_group,
    ranked.player_id,
    player.display_name,
    ranked.team,
    ranked.injury_status,
    ranked.games,
    ranked.role_volume,
    ranked.is_qualified,
    coalesce(week_status.week_complete, false) as week_complete,

    ranked.composite_score,
    ranked.efficiency_score,
    ranked.production_score,
    ranked.composite_rank,
    previous.composite_rank as composite_rank_prev,
    previous.composite_rank - ranked.composite_rank as composite_movement,
    ranked.composite_rank is not null
        and previous.composite_rank is null
        and ranked.week > ranked.season_first_week as composite_is_new,

    ranked.ppr_points,
    ranked.ppr_points / nullif(ranked.games, 0) as ppr_per_game,
    ranked.fantasy_rank,
    previous.fantasy_rank as fantasy_rank_prev,
    previous.fantasy_rank - ranked.fantasy_rank as fantasy_movement,
    ranked.fantasy_rank is not null
        and previous.fantasy_rank is null
        and ranked.week > ranked.season_first_week as fantasy_is_new
from ranked
left join ranked as previous
    on ranked.season = previous.season
    and ranked.week - 1 = previous.week
    and ranked.player_id = previous.player_id
    and ranked.position_group = previous.position_group
left join {{ ref('dim_player') }} as player on ranked.player_id = player.player_id
left join week_status
    on ranked.season = week_status.season and ranked.week = week_status.week
