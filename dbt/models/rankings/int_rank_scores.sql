-- Blends each qualified player's metric percentiles into efficiency, production, and composite
-- scores (0 to 100). One row per ranked-position player per week, including players who are not
-- qualified (their scores are null).
--
-- A player missing a metric (a running back with no targets has no receiving efficiency) is scored
-- on the metrics they do have: the weights are renormalized over the metrics present.
with component_scores as (
    select
        season,
        week,
        player_id,
        100 * sum(weight * percentile) filter (where component = 'efficiency')
            / nullif(sum(weight) filter (where component = 'efficiency'), 0) as efficiency_score,
        100 * sum(weight * percentile) filter (where component = 'production')
            / nullif(sum(weight) filter (where component = 'production'), 0) as production_score
    from {{ ref('int_rank_percentiles') }}
    group by all
)

select
    metrics.season,
    metrics.week,
    metrics.player_id,
    metrics.position_group,
    metrics.team,
    metrics.injury_status,
    metrics.games,
    metrics.role_volume,
    metrics.is_qualified,
    metrics.ppr_points,
    scores.efficiency_score,
    scores.production_score,
    -- if a player somehow has only one component, score them on that one
    case
        when scores.efficiency_score is null then scores.production_score
        when scores.production_score is null then scores.efficiency_score
        else config.efficiency_weight * scores.efficiency_score
            + config.production_weight * scores.production_score
    end as composite_score
from {{ ref('int_rank_metrics') }} as metrics
inner join {{ ref('ranking_config') }} as config using (position_group)
left join component_scores as scores using (season, week, player_id)
