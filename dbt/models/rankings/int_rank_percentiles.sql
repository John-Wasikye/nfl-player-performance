-- One row per qualified player, week, and metric: the metric's value and its percentile (0 to 1)
-- among qualified players at the same position in the same week.
--
--   * "Qualified" means the player's role volume meets the position's minimum for the week
--     (min_role_per_week in ranking_config, times the week number).
--   * A metric where lower is better (sack rate, interception rate) is flipped so a low value
--     earns a high percentile.
--   * Players with a null value for a metric (no targets, no attempts) get no row for it.
--   * With a single qualified player the percentile is 0.5 rather than an undefined 0.
{% set metrics = ranking_metrics() %}

with players as (
    select
        m.season,
        m.week,
        m.player_id,
        m.position_group,
        {% for metric in metrics %}m.{{ metric }}::double as {{ metric }},
        {% endfor %}
        m.is_qualified
    from {{ ref('int_rank_metrics') }} as m
),

metric_rows as (
    unpivot players
    on {{ metrics | join(', ') }}
    into name metric value metric_value
),

weighted as (
    select
        metric_rows.season,
        metric_rows.week,
        metric_rows.player_id,
        metric_rows.position_group,
        metric_rows.metric,
        metric_rows.metric_value,
        weights.component,
        weights.direction,
        weights.weight
    from metric_rows
    inner join {{ ref('ranking_weights') }} as weights
        on metric_rows.position_group = weights.position_group
        and metric_rows.metric = weights.metric
    where metric_rows.is_qualified
        and metric_rows.metric_value is not null
        and not isnan(metric_rows.metric_value)
)

select
    *,
    case
        when count(*) over (partition by season, week, position_group, metric) = 1 then 0.5
        else percent_rank() over (
            partition by season, week, position_group, metric
            order by case when direction = 'lower' then -metric_value else metric_value end
        )
    end as percentile
from weighted
