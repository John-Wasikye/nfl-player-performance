-- The feature store holds both played games and the upcoming week's fixtures, so `actual_ppr`
-- cannot simply be required to be non-null. The real rule is tighter and worth stating exactly:
-- a row has an outcome precisely when its game has finished.
--
-- Both directions matter. A missing outcome on a finished game would silently shrink every
-- training set and every graded week. An outcome present on an unfinished game would mean the
-- store had somehow seen the future, which is the one thing this model must never do.
select
    feat.player_id,
    feat.season,
    feat.week,
    game.is_final,
    feat.actual_ppr
from {{ ref('feat_player_week') }} as feat
inner join {{ ref('dim_game') }} as game
    on game.game_id = feat.game_id
where game.is_final != (feat.actual_ppr is not null)
