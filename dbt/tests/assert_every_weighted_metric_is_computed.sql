-- Every metric named in the ranking_weights seed must be one the ranking models compute (the list in
-- macros/ranking_metrics.sql). Otherwise a typo in the seed would silently drop that metric.
{% set known = ranking_metrics() %}
select distinct position_group, metric
from {{ ref('ranking_weights') }}
where metric not in ({% for metric in known %}'{{ metric }}'{% if not loop.last %}, {% endif %}{% endfor %})
