-- One row per player per week of the richer signals the box score does not carry: how often they
-- were on the field, how often they ran a route, how efficiently they were used, and what style of
-- offense they played in.
--
-- Coverage differs by source, so every column is optional and downstream models must tolerate nulls:
--   participation  2016-2025 (not published for the current season)
--   advanced stats 2018 onward, including the current season
--   FTN charting   2022 onward, including the current season
with snaps as (
    select
        p.player_id,
        game.season,
        game.week,
        count(*) as snaps,
        count(*) filter (where p.is_dropback) as pass_snaps,
        avg(p.defenders_in_box) as avg_defenders_in_box,
        avg(p.number_of_pass_rushers) as avg_pass_rushers_faced
    from {{ ref('stg_participation') }} as p
    inner join {{ ref('dim_game') }} as game on p.game_id = game.game_id
    where game.game_type = 'REG'
    group by all
),

team_snaps as (
    -- The team's own offensive snaps for the week: the count of distinct plays it had the ball for.
    -- (Using the busiest player's snap count instead would let a share exceed 1.)
    select game.season, game.week, p.team, count(distinct p.play_id) as team_plays
    from {{ ref('stg_participation') }} as p
    inner join {{ ref('dim_game') }} as game on p.game_id = game.game_id
    where game.game_type = 'REG'
    group by all
),

advanced as (
    select
        player.player_id,
        adv.season,
        adv.week,
        adv.rushing_yards_before_contact_avg,
        adv.rushing_yards_after_contact_avg,
        adv.rushing_broken_tackles,
        adv.receiving_broken_tackles,
        adv.receiving_drop,
        adv.receiving_drop_pct,
        adv.times_pressured_pct,
        adv.times_blitzed,
        adv.passing_bad_throw_pct
    from {{ ref('stg_advstats') }} as adv
    inner join {{ ref('dim_player') }} as player on adv.pfr_player_id = player.pfr_id
),

-- How a team plays, from the charting: this is context for every one of its players.
team_style as (
    select
        ftn.season,
        ftn.week,
        pbp.posteam as team,
        avg(ftn.is_play_action::int) as play_action_rate,
        avg(ftn.is_no_huddle::int) as no_huddle_rate,
        avg(ftn.is_motion::int) as motion_rate,
        avg(ftn.is_screen_pass::int) as screen_rate,
        avg(ftn.is_rpo::int) as rpo_rate
    from {{ ref('stg_ftn_charting') }} as ftn
    inner join {{ ref('stg_pbp_plays') }} as pbp
        on ftn.game_id = pbp.game_id and ftn.play_id = pbp.play_id
    where pbp.posteam is not null
    group by all
)

select
    fct.player_id,
    fct.season,
    fct.week,
    fct.position_group,
    fct.team,

    snaps.snaps,
    snaps.pass_snaps,
    -- share of the team's offensive snaps for the week
    snaps.snaps::double / nullif(team_snaps.team_plays, 0) as snap_share,
    -- targets per pass snap: the public stand-in for target-per-route-run
    fct.targets::double / nullif(snaps.pass_snaps, 0) as target_per_pass_snap,
    fct.receiving_yards::double / nullif(snaps.pass_snaps, 0) as yards_per_pass_snap,
    snaps.avg_defenders_in_box,
    snaps.avg_pass_rushers_faced,

    advanced.rushing_yards_before_contact_avg,
    advanced.rushing_yards_after_contact_avg,
    advanced.rushing_broken_tackles,
    advanced.receiving_broken_tackles,
    advanced.receiving_drop,
    advanced.receiving_drop_pct,
    advanced.times_pressured_pct,
    advanced.times_blitzed,
    advanced.passing_bad_throw_pct,

    team_style.play_action_rate,
    team_style.no_huddle_rate,
    team_style.motion_rate,
    team_style.screen_rate,
    team_style.rpo_rate
from {{ ref('fct_player_week') }} as fct
left join snaps using (player_id, season, week)
left join team_snaps on fct.season = team_snaps.season
    and fct.week = team_snaps.week and fct.team = team_snaps.team
left join advanced using (player_id, season, week)
left join team_style on fct.season = team_style.season
    and fct.week = team_style.week and fct.team = team_style.team
where fct.season_type = 'REG'
