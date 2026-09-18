-- Fantasy points scored by each player in each week: PPR for everyone except kickers.
-- nflverse does not score kickers, so they get common standard scoring: field goals are worth
-- 3 points (under 40 yards), 4 (40-49) or 5 (50+), extra points 1, and each miss -1.
-- Used by the rankings (season-to-date points) and by the backtest (next-week points).
select
    fct.season,
    fct.week,
    fct.season_type,
    fct.player_id,
    fct.position_group,
    case
        when fct.position_group = 'K' then
            3 * (coalesce(fct.fg_made_0_19, 0) + coalesce(fct.fg_made_20_29, 0)
                + coalesce(fct.fg_made_30_39, 0))
            + 4 * coalesce(fct.fg_made_40_49, 0)
            + 5 * (coalesce(fct.fg_made_50_59, 0) + coalesce(fct.fg_made_60_, 0))
            + coalesce(fct.pat_made, 0)
            - coalesce(fct.fg_missed, 0)
            - coalesce(fct.pat_missed, 0)
        else fct.fantasy_points_ppr
    end as fantasy_points_scored
from {{ ref('fct_player_week') }} as fct
