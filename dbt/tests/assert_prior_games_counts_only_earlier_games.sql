-- prior_games should equal exactly the number of earlier games that player has in the store. If a
-- window were off by one in either direction, this catches it.
with expected as (
    select
        player_id,
        season,
        week,
        row_number() over (partition by player_id order by season, week) - 1 as expected_prior
    from {{ ref('feat_player_week') }}
)

select
    feat.player_id,
    feat.season,
    feat.week,
    feat.prior_games,
    expected.expected_prior
from {{ ref('feat_player_week') }} as feat
inner join expected using (player_id, season, week)
where feat.prior_games != expected.expected_prior
