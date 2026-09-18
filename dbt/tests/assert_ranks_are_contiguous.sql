-- Within each season, week, and position, ranks must run 1..N with no gaps or duplicates, for both
-- the composite and the fantasy view. Returns one row per broken group.
with composite as (
    select
        'composite' as view_name, season, week, position_group,
        count(composite_rank) as ranked_players,
        count(distinct composite_rank) as distinct_ranks,
        max(composite_rank) as highest_rank
    from {{ ref('mart_rankings') }}
    group by all
),

fantasy as (
    select
        'fantasy' as view_name, season, week, position_group,
        count(fantasy_rank) as ranked_players,
        count(distinct fantasy_rank) as distinct_ranks,
        max(fantasy_rank) as highest_rank
    from {{ ref('mart_rankings') }}
    group by all
)

select * from composite
where ranked_players > 0 and (distinct_ranks != ranked_players or highest_rank != ranked_players)
union all
select * from fantasy
where distinct_ranks != ranked_players or highest_rank != ranked_players
