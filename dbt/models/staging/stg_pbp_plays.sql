-- The handful of play-by-play columns other models need, so nothing else has to read the very wide
-- raw file (372 columns). Regular season only.
select
    game_id,
    play_id,
    season,
    week,
    posteam,
    defteam,
    play_type,
    qb_dropback,
    pass_attempt,
    rush_attempt,
    yardline_100,
    down,
    ydstogo,
    score_differential,
    epa,
    air_yards,
    receiver_player_id,
    rusher_player_id,
    passer_player_id,
    touchdown,
    pass_touchdown,
    rush_touchdown,
    td_player_id,
    complete_pass,
    yards_gained
from {{ latest_raw('pbp') }}
where season_type = 'REG'
