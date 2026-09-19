-- Who was on the field for each offensive snap, from nflverse participation data.
--
-- `offense_players` is a semicolon-separated list of the same player ids we use elsewhere, so one
-- row per play becomes one row per player per play. From this we can count a player's snaps and,
-- more usefully, their *pass snaps*: the standard public proxy for routes run, which is the most
-- stable receiving metric there is (see PREDICTION_RESEARCH_PAPER.md section 3).
--
-- Note: nflverse has not published participation for the current season, so this covers 2016-2025.
-- Anything built on it must tolerate the column being absent for live weeks.
with plays as (
    select
        nflverse_game_id as game_id,
        play_id,
        possession_team,
        offense_formation,
        offense_personnel,
        defenders_in_box,
        number_of_pass_rushers,
        was_pressure,
        offense_players
    from {{ latest_raw('participation') }}
    where offense_players is not null and offense_players != ''
),

exploded as (
    select
        plays.* exclude (offense_players),
        unnest(string_split(plays.offense_players, ';')) as player_id
    from plays
),

pbp as (
    select game_id, play_id, play_type, qb_dropback, pass_attempt
    from {{ ref('stg_pbp_plays') }}
)

select
    exploded.game_id,
    exploded.play_id,
    exploded.player_id,
    exploded.possession_team as team,
    exploded.offense_formation,
    exploded.offense_personnel,
    exploded.defenders_in_box,
    exploded.number_of_pass_rushers,
    exploded.was_pressure,
    pbp.play_type,
    coalesce(pbp.qb_dropback, 0) = 1 as is_dropback
from exploded
left join pbp on exploded.game_id = pbp.game_id and exploded.play_id = pbp.play_id
where exploded.player_id != ''
