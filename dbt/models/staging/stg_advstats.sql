-- Pro Football Reference weekly advanced stats, the three player-level files combined into one row
-- per player per week. These separate a player's own work from his situation: yards after contact
-- (the back, not the blocking), pressure faced (the line, not the quarterback), and drops.
--
-- Keyed by PFR's player id; dim_player carries the crosswalk to our ids.
with rush as (
    select
        season, week, game_id, pfr_player_id, team, opponent,
        carries as pfr_carries,
        rushing_yards_before_contact,
        rushing_yards_before_contact_avg,
        rushing_yards_after_contact,
        rushing_yards_after_contact_avg,
        rushing_broken_tackles
    from {{ latest_raw('advstats_rush') }}
    where game_type = 'REG'
),

rec as (
    select
        season, week, game_id, pfr_player_id,
        receiving_broken_tackles,
        receiving_drop,
        receiving_drop_pct,
        receiving_int,
        receiving_rat
    from {{ latest_raw('advstats_rec') }}
    where game_type = 'REG'
),

passing as (
    select
        season, week, game_id, pfr_player_id,
        passing_bad_throws,
        passing_bad_throw_pct,
        passing_drops as passing_drops_by_receivers,
        times_sacked,
        times_blitzed,
        times_hurried,
        times_hit,
        times_pressured,
        times_pressured_pct
    from {{ latest_raw('advstats_pass') }}
    where game_type = 'REG'
)

select
    coalesce(rush.season, rec.season, passing.season) as season,
    coalesce(rush.week, rec.week, passing.week) as week,
    coalesce(rush.game_id, rec.game_id, passing.game_id) as game_id,
    coalesce(rush.pfr_player_id, rec.pfr_player_id, passing.pfr_player_id) as pfr_player_id,
    rush.team,
    rush.opponent,
    rush.pfr_carries,
    rush.rushing_yards_before_contact,
    rush.rushing_yards_before_contact_avg,
    rush.rushing_yards_after_contact,
    rush.rushing_yards_after_contact_avg,
    rush.rushing_broken_tackles,
    rec.receiving_broken_tackles,
    rec.receiving_drop,
    rec.receiving_drop_pct,
    rec.receiving_rat,
    passing.passing_bad_throws,
    passing.passing_bad_throw_pct,
    passing.times_sacked,
    passing.times_blitzed,
    passing.times_hurried,
    passing.times_pressured,
    passing.times_pressured_pct
from rush
full outer join rec
    on rush.season = rec.season and rush.week = rec.week
    and rush.pfr_player_id = rec.pfr_player_id
full outer join passing
    on coalesce(rush.season, rec.season) = passing.season
    and coalesce(rush.week, rec.week) = passing.week
    and coalesce(rush.pfr_player_id, rec.pfr_player_id) = passing.pfr_player_id
