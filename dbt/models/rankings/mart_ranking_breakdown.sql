-- Explains each composite score: one row per qualified player, week, and metric.
-- contribution_points is how many of the player's 0-100 composite points come from this metric,
-- so the rows for one player-week add up to their composite_score (see the accompanying test).
with percentiles as (
    select
        p.*,
        sum(p.weight) over (partition by p.season, p.week, p.player_id, p.component)
            as component_weight_total
    from {{ ref('int_rank_percentiles') }} as p
),

with_config as (
    select
        percentiles.*,
        case percentiles.component
            when 'efficiency' then config.efficiency_weight
            else config.production_weight
        end as component_share,
        -- players with only one component are scored entirely on it
        count(distinct percentiles.component) over (
            partition by percentiles.season, percentiles.week, percentiles.player_id
        ) as components_present
    from percentiles
    inner join {{ ref('ranking_config') }} as config using (position_group)
)

select
    season,
    week,
    position_group,
    player_id,
    metric,
    component,
    metric_value,
    percentile,
    weight,
    100 * percentile * weight / component_weight_total
        * (case when components_present = 1 then 1 else component_share end) as contribution_points
from with_config
