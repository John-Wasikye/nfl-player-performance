-- Season-to-date totals for every ranked player, for every week they could have been ranked.
--
-- Rankings are computed "as of week N" using only games through week N, so there is no lookahead
-- (the backtest relies on this). A player appears in every week from their first game onward; on a
-- bye week their totals carry forward unchanged. Regular season only.
with ranked_positions as (
    select position_group from {{ ref('position_map') }} where is_ranked_v1
),

stat_lines as (
    select fct.*, points.fantasy_points_scored
    from {{ ref('fct_player_week') }} as fct
    inner join {{ ref('int_weekly_fantasy_points') }} as points
        on fct.player_id = points.player_id
        and fct.season = points.season
        and fct.week = points.week
    where fct.season_type = 'REG'
        and fct.position_group in (select position_group from ranked_positions)
),

weeks as (
    select distinct season, week from stat_lines
),

first_week as (
    select season, player_id, min(week) as first_week from stat_lines group by all
),

spine as (
    select weeks.season, weeks.week, first_week.player_id
    from weeks
    inner join first_week
        on weeks.season = first_week.season and weeks.week >= first_week.first_week
)

select
    spine.season,
    spine.week,
    spine.player_id,

    -- the position and team the player was most recently listed with
    last_value(stat_lines.position_group ignore nulls) over w as position_group,
    last_value(stat_lines.team ignore nulls) over w as team,
    -- only set when the player has a stat line in this exact week
    stat_lines.injury_status,

    count(stat_lines.week) over w as games,

    sum(coalesce(stat_lines.attempts, 0)) over w as attempts,
    sum(coalesce(stat_lines.completions, 0)) over w as completions,
    sum(coalesce(stat_lines.passing_yards, 0)) over w as passing_yards,
    sum(coalesce(stat_lines.passing_tds, 0)) over w as passing_tds,
    sum(coalesce(stat_lines.passing_interceptions, 0)) over w as passing_interceptions,
    sum(coalesce(stat_lines.sacks_suffered, 0)) over w as sacks_suffered,
    sum(coalesce(stat_lines.passing_epa, 0)) over w as passing_epa,
    -- CPOE is a per-game average, so accumulate it weighted by attempts
    sum(coalesce(stat_lines.passing_cpoe, 0) * coalesce(stat_lines.attempts, 0)) over w
        as passing_cpoe_x_attempts,

    sum(coalesce(stat_lines.carries, 0)) over w as carries,
    sum(coalesce(stat_lines.rushing_yards, 0)) over w as rushing_yards,
    sum(coalesce(stat_lines.rushing_tds, 0)) over w as rushing_tds,
    sum(coalesce(stat_lines.rushing_epa, 0)) over w as rushing_epa,
    sum(coalesce(stat_lines.rushing_first_downs, 0)) over w as rushing_first_downs,

    sum(coalesce(stat_lines.targets, 0)) over w as targets,
    sum(coalesce(stat_lines.receptions, 0)) over w as receptions,
    sum(coalesce(stat_lines.receiving_yards, 0)) over w as receiving_yards,
    sum(coalesce(stat_lines.receiving_tds, 0)) over w as receiving_tds,
    sum(coalesce(stat_lines.receiving_epa, 0)) over w as receiving_epa,
    sum(coalesce(stat_lines.receiving_air_yards, 0)) over w as receiving_air_yards,
    sum(coalesce(stat_lines.receiving_first_downs, 0)) over w as receiving_first_downs,
    -- shares and WOPR are per-game values, so accumulate the sum and divide by games later
    sum(coalesce(stat_lines.target_share, 0)) over w as target_share_sum,
    sum(coalesce(stat_lines.air_yards_share, 0)) over w as air_yards_share_sum,
    sum(coalesce(stat_lines.wopr, 0)) over w as wopr_sum,

    sum(coalesce(stat_lines.fg_att, 0)) over w as fg_att,
    sum(coalesce(stat_lines.fg_made, 0)) over w as fg_made,
    sum(coalesce(stat_lines.fg_made_40_49, 0)) over w as fg_made_40_49,
    sum(coalesce(stat_lines.fg_made_50_59, 0)) over w as fg_made_50_59,
    sum(coalesce(stat_lines.fg_made_60_, 0)) over w as fg_made_60_plus,
    sum(coalesce(stat_lines.fg_missed_40_49, 0)) over w as fg_missed_40_49,
    sum(coalesce(stat_lines.fg_missed_50_59, 0)) over w as fg_missed_50_59,
    sum(coalesce(stat_lines.fg_missed_60_, 0)) over w as fg_missed_60_plus,
    sum(coalesce(stat_lines.pat_att, 0)) over w as pat_att,
    sum(coalesce(stat_lines.pat_made, 0)) over w as pat_made,

    sum(coalesce(stat_lines.fantasy_points_scored, 0)) over w as ppr_points
from spine
left join stat_lines
    on spine.season = stat_lines.season
    and spine.week = stat_lines.week
    and spine.player_id = stat_lines.player_id
window w as (
    partition by spine.season, spine.player_id
    order by spine.week
    rows between unbounded preceding and current row
)
