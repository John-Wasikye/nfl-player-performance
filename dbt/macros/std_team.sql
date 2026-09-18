{# Standardize a team code using the team_map seed (for example OAK -> LV, SD -> LAC). #}
{% macro std_team(column, alias) -%}
coalesce({{ alias }}.team_code, {{ column }})
{%- endmacro %}
