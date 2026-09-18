{# Fails for every row where the expression is false. Rows where it is NULL pass. #}
{% test expression_is_true(model, expression, column_name=None, where=None) %}
select *
from {{ model }}
where not ({{ expression }})
{% if where %} and ({{ where }}) {% endif %}
{% endtest %}
