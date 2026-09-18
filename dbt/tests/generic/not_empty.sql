{% test not_empty(model) %}
select 'model has no rows' as problem
where (select count(*) from {{ model }}) = 0
{% endtest %}
