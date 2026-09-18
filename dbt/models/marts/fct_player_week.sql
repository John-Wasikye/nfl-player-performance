-- One row per player per week: the weekly stat line plus the game, snap share, and injury status.
-- position_group is the position the player was listed at for that week (not their career position).
with stats as (
    select * from {{ ref('stg_player_stats') }}
),

games as (
    select game_id, season, week, home_team, away_team from {{ ref('dim_game') }}
),

pfr_ids as (
    select player_id, pfr_id from {{ ref('dim_player') }} where pfr_id is not null
),

snaps as (
    select
        pfr_ids.player_id,
        snap.season,
        snap.week,
        snap.offense_snaps,
        snap.offense_pct,
        snap.defense_snaps,
        snap.defense_pct,
        snap.st_snaps,
        snap.st_pct
    from {{ ref('stg_snap_counts') }} as snap
    inner join pfr_ids on snap.pfr_player_id = pfr_ids.pfr_id
    qualify row_number() over (
        partition by pfr_ids.player_id, snap.season, snap.week
        order by snap.offense_snaps desc nulls last
    ) = 1
),

injuries as (
    select player_id, season, week, report_status as injury_status from {{ ref('stg_injuries') }}
)

select
    stats.* exclude (team, opponent_team),
    stats.team,
    stats.opponent_team,
    games.game_id,
    snaps.offense_snaps,
    snaps.offense_pct,
    snaps.defense_snaps,
    snaps.defense_pct,
    snaps.st_snaps,
    snaps.st_pct,
    injuries.injury_status
from stats
left join games
    on stats.season = games.season
    and stats.week = games.week
    and stats.team in (games.home_team, games.away_team)
left join snaps
    on stats.player_id = snaps.player_id
    and stats.season = snaps.season
    and stats.week = snaps.week
left join injuries
    on stats.player_id = injuries.player_id
    and stats.season = injuries.season
    and stats.week = injuries.week
