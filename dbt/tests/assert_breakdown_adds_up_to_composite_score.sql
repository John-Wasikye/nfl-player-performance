-- The per-metric contributions must add up to each player's composite score, so the "why this rank"
-- explanation on the site can never disagree with the score itself. (Scores are rounded to 6
-- decimals, so allow a hair more than that.)
with breakdown as (
    select season, week, player_id, sum(contribution_points) as total_points
    from {{ ref('mart_ranking_breakdown') }}
    group by all
)

select
    rankings.season,
    rankings.week,
    rankings.player_id,
    rankings.composite_score,
    breakdown.total_points
from {{ ref('mart_rankings') }} as rankings
inner join breakdown using (season, week, player_id)
where abs(rankings.composite_score - breakdown.total_points) > 0.00001
