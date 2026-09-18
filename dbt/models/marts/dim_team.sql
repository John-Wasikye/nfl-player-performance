select
    team_code,
    team_name,
    conference,
    division
from {{ ref('teams') }}
