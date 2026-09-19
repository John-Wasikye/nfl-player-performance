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

-- The week we are about to predict: the earliest one in the latest season that still has an
-- unplayed game. A week that is part-finished is still the upcoming week, because that is the week
-- a reader visiting mid-week wants projections for.
next_week as (
    select season, min(week) as week
    from {{ ref('dim_game') }}
    where game_type = 'REG'
      and not is_final
      and season = (select max(season) from {{ ref('dim_game') }} where game_type = 'REG')
    group by season
),

-- Who is on each team for that week, from the published roster for that exact week.
--
-- An earlier version inferred this from who had played recently, and it was wrong in a way worth
-- recording: "has not appeared in a box score lately" and "is not on the team" are indistinguishable
-- in stats data, so retired players kept being projected. Philip Rivers, whose last game was in
-- 2025, was being projected for 2026 because the recency bound compared `season * 100 + week`
-- values, and that is not a distance — the gap from 2025 week 17 to 2026 week 2 came out as 85,
-- smaller than the 120 the rule allowed, so an entire offseason counted as no time at all.
--
-- The roster file answers the question directly and needs no arithmetic. Only active players are
-- projected: a practice-squad player can be elevated but has no expected role, and anyone on
-- reserve, retired or released should not appear at all.
current_roster as (
    select
        roster.player_id,
        roster.team,
        position.position_group
    from {{ ref('stg_weekly_rosters') }} as roster
    inner join next_week
        on roster.season = next_week.season
        and roster.week = next_week.week
    -- The roster's own position field is spelled differently from the one the rest of the project
    -- uses, so the grouping comes from the player dimension, which is where that mapping lives.
    inner join {{ ref('dim_player') }} as position
        on position.player_id = roster.player_id
    where roster.is_active
      and position.position_group in ('QB', 'RB', 'WR', 'TE', 'K')
),

-- One row per player in that week's fixtures, with no statistics at all. Everything these rows
-- carry is either from the schedule (known in advance) or computed from earlier games by the
-- windows below, so an upcoming row is exactly as point-in-time as a historical one.
upcoming as (
    select
        roster.player_id,
        next_week.season,
        next_week.week,
        roster.position_group,
        roster.team,
        case when game.home_team = roster.team then game.away_team else game.home_team end
            as opponent_team,
        game.game_id,
        injury.report_status as injury_status,
        cast(null as double) as ppr,
        cast(null as integer) as attempts,
        cast(null as integer) as carries,
        cast(null as integer) as targets,
        cast(null as integer) as receptions,
        cast(null as integer) as passing_yards,
        cast(null as integer) as rushing_yards,
        cast(null as integer) as receiving_yards,
        cast(null as double) as target_share,
        cast(null as double) as snap_share,
        cast(null as integer) as pass_snaps,
        cast(null as double) as target_per_pass_snap,
        cast(null as double) as avg_separation,
        cast(null as double) as rush_yards_over_expected_per_att,
        cast(null as double) as completion_percentage_above_expectation,
        cast(null as double) as times_pressured_pct,
        cast(null as double) as rushing_yards_after_contact_avg
    from next_week
    inner join {{ ref('dim_game') }} as game
        on game.season = next_week.season
        and game.week = next_week.week
        and game.game_type = 'REG'
    inner join current_roster as roster
        on roster.team in (game.home_team, game.away_team)
    left join {{ ref('stg_injuries') }} as injury
        on injury.player_id = roster.player_id
        and injury.season = next_week.season
        and injury.week = next_week.week
    -- A player whose game that week has already finished is in `base` with his real result; adding
    -- him here too would duplicate him and, worse, give the duplicate a null outcome.
    where not game.is_final
),

combined as (
    select * from base
    union all
    select * from upcoming
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
    from combined
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
