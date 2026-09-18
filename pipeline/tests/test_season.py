from datetime import date

import pytest

from nfl_pipeline.season import current_season, parse_seasons


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 9, 18), 2026),  # regular season
        (date(2026, 12, 31), 2026),
        (date(2027, 1, 15), 2026),  # playoffs belong to the season that began in 2026
        (date(2027, 2, 28), 2026),  # Super Bowl
        (date(2027, 3, 1), 2027),  # offseason points at the upcoming season
        (date(2026, 8, 15), 2026),  # preseason
    ],
)
def test_current_season(today, expected):
    assert current_season(today) == expected


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("2026", [2026]),
        ("2024,2025", [2024, 2025]),
        ("2021-2023", [2021, 2022, 2023]),
        ("2025, 2021-2022, 2025", [2021, 2022, 2025]),  # sorted and de-duplicated
    ],
)
def test_parse_seasons(spec, expected):
    assert parse_seasons(spec) == expected


@pytest.mark.parametrize("spec", ["", " , ", "2025-2021", "abc"])
def test_parse_seasons_rejects_bad_input(spec):
    with pytest.raises(ValueError):
        parse_seasons(spec)
