{#
  Read the newest raw snapshot of an ingested dataset.

  The ingest writes each download to raw/<dataset>/[season=<year>/]ingest_date=<date>/<file>.parquet
  and never deletes older snapshots, so this keeps only the files from the latest ingest_date
  within each season (or overall, for datasets that are not split by season).
  Adds `_ingest_date` so downstream models can trace where a row came from.
#}
{% macro latest_raw(dataset) %}
(
    select * exclude (filename, _path_season)
    from (
        select
            *,
            cast(regexp_extract(filename, 'ingest_date=([0-9]{4}-[0-9]{2}-[0-9]{2})', 1) as date)
                as _ingest_date,
            regexp_extract(filename, 'season=([0-9]{4})', 1) as _path_season
        from read_parquet(
            '{{ var("raw_root") }}/{{ dataset }}/**/*.parquet',
            filename = true,
            hive_partitioning = false,
            union_by_name = true
        )
    )
    qualify _ingest_date = max(_ingest_date) over (partition by _path_season)
)
{% endmacro %}
