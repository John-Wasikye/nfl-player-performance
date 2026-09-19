-- Next Gen Stats: measures derived from player tracking that no box score contains - how open a
-- receiver gets, how much of the team's intended air yards he commands, how many yards a back gains
-- over what his carries should have produced, and how accurate a quarterback is versus expectation.
--
-- Unlike participation data, these files are refreshed during the season, so they are usable for
-- live predictions. Week 0 rows are season totals and are excluded.
with receiving as (
    select
        player_gsis_id as player_id, season, week,
        avg_cushion, avg_separation, avg_intended_air_yards as avg_target_depth,
        percent_share_of_intended_air_yards as air_yards_share_ngs,
        catch_percentage, avg_yac, avg_expected_yac, avg_yac_above_expectation
    from {{ latest_raw('ngs_receiving') }}
    where season_type = 'REG' and week > 0 and player_gsis_id is not null
),

rushing as (
    select
        player_gsis_id as player_id, season, week,
        efficiency as rush_efficiency,
        percent_attempts_gte_eight_defenders as pct_vs_stacked_box,
        avg_time_to_los,
        rush_yards_over_expected,
        rush_yards_over_expected_per_att,
        rush_pct_over_expected
    from {{ latest_raw('ngs_rushing') }}
    where season_type = 'REG' and week > 0 and player_gsis_id is not null
),

passing as (
    select
        player_gsis_id as player_id, season, week,
        avg_time_to_throw, avg_completed_air_yards,
        avg_intended_air_yards as avg_intended_air_yards_pass,
        aggressiveness, avg_air_yards_to_sticks,
        expected_completion_percentage,
        completion_percentage_above_expectation
    from {{ latest_raw('ngs_passing') }}
    where season_type = 'REG' and week > 0 and player_gsis_id is not null
)

select
    coalesce(receiving.player_id, rushing.player_id, passing.player_id) as player_id,
    coalesce(receiving.season, rushing.season, passing.season) as season,
    coalesce(receiving.week, rushing.week, passing.week) as week,
    receiving.avg_cushion,
    receiving.avg_separation,
    receiving.avg_target_depth,
    receiving.air_yards_share_ngs,
    receiving.avg_yac_above_expectation,
    rushing.rush_efficiency,
    rushing.pct_vs_stacked_box,
    rushing.avg_time_to_los,
    rushing.rush_yards_over_expected,
    rushing.rush_yards_over_expected_per_att,
    passing.avg_time_to_throw,
    passing.aggressiveness,
    passing.avg_air_yards_to_sticks,
    passing.completion_percentage_above_expectation
from receiving
full outer join rushing using (player_id, season, week)
full outer join passing using (player_id, season, week)
