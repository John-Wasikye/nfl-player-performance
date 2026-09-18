-- The official injury report status for a player in a week. If a player appears more than once in
-- a week (for example after a team change), keep the entry with the most severe report status.
with raw as (
    select * from {{ latest_raw('injuries') }}
    where gsis_id is not null
)

select
    gsis_id as player_id,
    season,
    week,
    report_status,
    report_primary_injury,
    practice_status
from raw
qualify row_number() over (
    partition by gsis_id, season, week
    order by
        case report_status
            when 'Out' then 1
            when 'Doubtful' then 2
            when 'Questionable' then 3
            else 4
        end,
        team
) = 1
