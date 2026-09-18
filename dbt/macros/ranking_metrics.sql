{# The metrics the ranking models can compute. ranking_weights may only name metrics from this list. #}
{% macro ranking_metrics() %}
{{ return([
    'epa_per_dropback', 'cpoe', 'yards_per_attempt', 'sack_rate', 'int_rate',
    'passing_epa', 'passing_yards', 'passing_tds',
    'rushing_epa_per_carry', 'yards_per_carry', 'rushing_yards', 'carries', 'total_tds',
    'first_downs',
    'receiving_epa_per_target', 'racr', 'yards_per_target', 'catch_rate', 'targets',
    'receptions', 'receiving_yards', 'receiving_tds', 'target_share_avg',
    'air_yards_share_avg', 'wopr_avg',
    'fg_pct', 'fg_pct_40_plus', 'pat_pct', 'fg_made', 'fg_made_50_plus', 'kicker_points',
]) }}
{% endmacro %}
