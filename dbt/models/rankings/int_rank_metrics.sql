-- Turns season-to-date totals into the metrics the rankings use. One row per player per week.
--
-- Every metric is computed for every player (null when it does not apply, for example a rate with
-- no attempts). The ranking_weights seed decides which metrics each position actually uses.
-- "Efficiency" metrics are rates per opportunity; "production" metrics are totals or per-game shares.
with metrics as (
    select
        season,
        week,
        player_id,
        position_group,
        team,
        injury_status,
        games,
        ppr_points,

        -- the volume that decides whether a player is ranked at all
        case position_group
            when 'QB' then attempts
            when 'RB' then carries + targets
            when 'WR' then targets
            when 'TE' then targets
            when 'K' then fg_att + pat_att
        end as role_volume,

        -- quarterback
        passing_epa / nullif(attempts + sacks_suffered, 0) as epa_per_dropback,
        passing_cpoe_x_attempts / nullif(attempts, 0) as cpoe,
        passing_yards::double / nullif(attempts, 0) as yards_per_attempt,
        sacks_suffered::double / nullif(attempts + sacks_suffered, 0) as sack_rate,
        passing_interceptions::double / nullif(attempts, 0) as int_rate,
        passing_epa,
        passing_yards,
        passing_tds,

        -- rushing
        rushing_epa / nullif(carries, 0) as rushing_epa_per_carry,
        rushing_yards::double / nullif(carries, 0) as yards_per_carry,
        rushing_yards,
        carries,
        rushing_tds + receiving_tds as total_tds,
        rushing_first_downs + receiving_first_downs as first_downs,

        -- receiving
        receiving_epa / nullif(targets, 0) as receiving_epa_per_target,
        -- RACR: receiving yards per air yard; undefined when air yards are zero or negative
        case when receiving_air_yards > 0 then receiving_yards::double / receiving_air_yards end as racr,
        receiving_yards::double / nullif(targets, 0) as yards_per_target,
        receptions::double / nullif(targets, 0) as catch_rate,
        targets,
        receptions,
        receiving_yards,
        receiving_tds,
        target_share_sum / nullif(games, 0) as target_share_avg,
        air_yards_share_sum / nullif(games, 0) as air_yards_share_avg,
        wopr_sum / nullif(games, 0) as wopr_avg,

        -- Next Gen Stats (tracking): skill separated from opportunity. Null until a player has
    -- appeared in an NGS week, which is about 90-96% of ranked players.
    separation_x_targets / nullif(targets_with_separation, 0) as avg_separation,
    yac_oe_x_receptions / nullif(receptions_with_yac_oe, 0) as yac_over_expected,
    ryoe_x_carries / nullif(carries_with_ryoe, 0) as rush_yards_over_expected_per_att,

    -- kicker
        fg_made::double / nullif(fg_att, 0) as fg_pct,
        (fg_made_40_49 + fg_made_50_59 + fg_made_60_plus)::double
            / nullif(
                fg_made_40_49 + fg_made_50_59 + fg_made_60_plus
                + fg_missed_40_49 + fg_missed_50_59 + fg_missed_60_plus,
                0
            ) as fg_pct_40_plus,
        pat_made::double / nullif(pat_att, 0) as pat_pct,
        fg_made,
        fg_made_50_59 + fg_made_60_plus as fg_made_50_plus,
        fg_made * 3 + pat_made as kicker_points
    from {{ ref('int_cumulative_stats') }}
)

-- Games each team has finished through each week (bye weeks carry the count forward).
, final_team_games as (
    select season, week, home_team as team from {{ ref('dim_game') }}
    where game_type = 'REG' and is_final
    union all
    select season, week, away_team as team from {{ ref('dim_game') }}
    where game_type = 'REG' and is_final
),

team_weeks as (
    select distinct season, week, team from metrics where team is not null
),

team_games as (
    select
        team_weeks.season,
        team_weeks.week,
        team_weeks.team,
        count(final_team_games.week) as team_games
    from team_weeks
    left join final_team_games
        on team_weeks.season = final_team_games.season
        and team_weeks.team = final_team_games.team
        and final_team_games.week <= team_weeks.week
    group by all
)

select
    metrics.*,
    team_games.team_games,
    -- ranked only with enough volume for the games the player's team has played:
    -- min_role_per_week * team games. Counting games (not the week number) keeps players fair
    -- while a week is still in progress or after a bye.
    metrics.role_volume >= config.min_role_per_week * greatest(team_games.team_games, 1)
        as is_qualified
from metrics
inner join {{ ref('ranking_config') }} as config using (position_group)
left join team_games
    on metrics.season = team_games.season
    and metrics.week = team_games.week
    and metrics.team = team_games.team
