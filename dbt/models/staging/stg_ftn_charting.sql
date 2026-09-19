-- FTN's manual play charting (2022 onward): how a play was designed rather than how it turned out.
-- Play action, screens, motion, no-huddle and blitz counts describe an offense's style, which the
-- box score never shows.
select
    nflverse_game_id as game_id,
    nflverse_play_id as play_id,
    season,
    week,
    qb_location,
    n_offense_backfield,
    n_defense_box,
    n_blitzers,
    n_pass_rushers,
    is_no_huddle,
    is_motion,
    is_play_action,
    is_screen_pass,
    is_rpo,
    is_qb_out_of_pocket,
    is_catchable_ball,
    is_contested_ball,
    is_created_reception,
    is_drop
from {{ latest_raw('ftn_charting') }}
