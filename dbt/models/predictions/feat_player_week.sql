-- The feature store: one row per player per week containing **only what was knowable before that
-- week's game kicked off**.
--
-- This is the most safety-critical model in the project. Every accuracy figure we ever publish
-- rests on the claim that a week's features never saw that week's result, or any later one. So the
-- rule here is absolute: every measure taken from a player's own play is shifted back by one game
-- before it is used, and nothing reads the current row's outcome.
--
-- Things that ARE known before kickoff and so may be used as-is: the schedule, the betting line,
-- the roof and forecast, rest days, and the injury report.
--
-- The leakage rule is enforced three ways: `rows between unbounded preceding and 1 preceding`
-- windows here, a dbt test that no trailing measure equals its own week's value across the board,
-- and a Python test that changing a future week's result leaves earlier features byte-identical.
with base as (
    select
        fct.player_id,
        fct.season,
        fct.week,
        fct.position_group,
        fct.team,
        fct.opponent_team,
        fct.game_id,
        fct.injury_status,
        points.fantasy_points_scored as ppr,
        fct.attempts,
        fct.carries,
        fct.targets,
        fct.receptions,
        fct.passing_yards,
        fct.rushing_yards,
        fct.receiving_yards,
        coalesce(fct.target_share, 0) as target_share,
        adv.snap_share,
        adv.pass_snaps,
        adv.target_per_pass_snap,
        adv.avg_separation,
        adv.rush_yards_over_expected_per_att,
        adv.completion_percentage_above_expectation,
        adv.times_pressured_pct,
        adv.rushing_yards_after_contact_avg
    from {{ ref('fct_player_week') }} as fct
    inner join {{ ref('int_weekly_fantasy_points') }} as points
        using (player_id, season, week)
    left join {{ ref('fct_player_week_advanced') }} as adv
        using (player_id, season, week)
    where fct.season_type = 'REG'
      and fct.position_group in ('QB', 'RB', 'WR', 'TE', 'K')
),

-- Every backward-looking window ends one game BEFORE the current row. Recent form carries across seasons
-- (a player does not become a stranger in September), but the season average resets.
player_form as (
    select
        *,
        count(*) over prior as prior_games,
        avg(ppr) over prior_3 as ppr_mean3,
        avg(ppr) over prior_5 as ppr_mean5,
        avg(ppr) over prior_10 as ppr_mean10,
        stddev_samp(ppr) over prior_8 as ppr_std8,
        avg(ppr) over prior_season as ppr_season_avg,

        avg(attempts) over prior_5 as attempts_mean5,
        avg(carries) over prior_5 as carries_mean5,
        avg(targets) over prior_5 as targets_mean5,
        avg(receptions) over prior_5 as receptions_mean5,
        avg(target_share) over prior_5 as target_share_mean5,
        avg(passing_yards) over prior_5 as passing_yards_mean5,
        avg(rushing_yards) over prior_5 as rushing_yards_mean5,
        avg(receiving_yards) over prior_5 as receiving_yards_mean5,

        avg(snap_share) over prior_5 as snap_share_mean5,
        avg(pass_snaps) over prior_5 as pass_snaps_mean5,
        avg(target_per_pass_snap) over prior_5 as target_per_pass_snap_mean5,
        avg(avg_separation) over prior_8 as separation_mean8,
        avg(rush_yards_over_expected_per_att) over prior_8 as ryoe_mean8,
        avg(completion_percentage_above_expectation) over prior_8 as cpoe_mean8,
        avg(times_pressured_pct) over prior_8 as pressure_rate_mean8,
        avg(rushing_yards_after_contact_avg) over prior_8 as yac_contact_mean8
    from base
    window
        prior as (
            partition by player_id order by season, week
            rows between unbounded preceding and 1 preceding
        ),
        prior_3 as (
            partition by player_id order by season, week rows between 3 preceding and 1 preceding
        ),
        prior_5 as (
            partition by player_id order by season, week rows between 5 preceding and 1 preceding
        ),
        prior_8 as (
            partition by player_id order by season, week rows between 8 preceding and 1 preceding
        ),
        prior_10 as (
            partition by player_id order by season, week rows between 10 preceding and 1 preceding
        ),
        prior_season as (
            partition by player_id, season order by week
            rows between unbounded preceding and 1 preceding
        )
),

-- What a defence has been giving up to this position, again using only earlier weeks.
opponent as (
    select
        season,
        week,
        defense,
        position_group,
        avg(points_allowed) over (
            partition by defense, position_group order by season, week
            rows between 8 preceding and 1 preceding
        ) as points_allowed_to_position_mean8
    from (
        select
            fct.season,
            fct.week,
            fct.opponent_team as defense,
            fct.position_group,
            sum(points.fantasy_points_scored) as points_allowed
        from {{ ref('fct_player_week') }} as fct
        inner join {{ ref('int_weekly_fantasy_points') }} as points
            using (player_id, season, week)
        where fct.season_type = 'REG'
          and fct.position_group in ('QB', 'RB', 'WR', 'TE', 'K')
        group by all
    )
),

game as (
    select
        game_id,
        season,
        week,
        home_team,
        away_team,
        spread_line,
        total_line,
        home_rest,
        away_rest,
        is_divisional,
        roof,
        temp,
        wind
    from {{ ref('dim_game') }}
    where game_type = 'REG'
)

select
    player_form.player_id,
    player_form.season,
    player_form.week,
    player_form.position_group,
    player_form.team,
    player_form.opponent_team,
    player_form.game_id,

    -- the outcome, carried alongside for training and grading; never an input
    player_form.ppr as actual_ppr,

    -- player form and usage, all strictly before this week
    player_form.prior_games,
    player_form.ppr_mean3,
    player_form.ppr_mean5,
    player_form.ppr_mean10,
    player_form.ppr_std8,
    player_form.ppr_season_avg,
    player_form.attempts_mean5,
    player_form.carries_mean5,
    player_form.targets_mean5,
    player_form.receptions_mean5,
    player_form.target_share_mean5,
    player_form.passing_yards_mean5,
    player_form.rushing_yards_mean5,
    player_form.receiving_yards_mean5,
    player_form.snap_share_mean5,
    player_form.pass_snaps_mean5,
    player_form.target_per_pass_snap_mean5,
    player_form.separation_mean8,
    player_form.ryoe_mean8,
    player_form.cpoe_mean8,
    player_form.pressure_rate_mean8,
    player_form.yac_contact_mean8,

    -- the game, known once the schedule and line are published
    game.home_team = player_form.team as is_home,
    case when game.home_team = player_form.team then game.spread_line else -game.spread_line end
        as team_spread,
    game.total_line,
    game.total_line / 2
        + case when game.home_team = player_form.team then game.spread_line else -game.spread_line end
        / 2 as implied_team_total,
    case when game.home_team = player_form.team then game.home_rest else game.away_rest end as rest_days,
    game.is_divisional,
    game.roof in ('dome', 'closed') as is_indoors,
    case when game.roof in ('dome', 'closed') then 0 else game.wind end as wind,
    case when game.roof in ('dome', 'closed') then 70 else game.temp end as temp,

    -- the opponent, from their earlier weeks only
    opponent.points_allowed_to_position_mean8,

    -- the injury report, published before kickoff
    player_form.injury_status,
    player_form.injury_status = 'Questionable' as is_questionable
from player_form
left join game on player_form.game_id = game.game_id
left join opponent
    on player_form.season = opponent.season
    and player_form.week = opponent.week
    and player_form.opponent_team = opponent.defense
    and player_form.position_group = opponent.position_group
