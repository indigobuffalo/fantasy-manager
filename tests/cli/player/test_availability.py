import pytest
from hamcrest import assert_that, equal_to, contains_inanyorder

from fantasy_manager.cli.player.availability import (
    _PLAYER_RE,
    _ROW_RE,
    Availability,
    league_label,
    ownership,
    resolve_league_ids,
    resolve_workers,
)
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import InputError


def test_league_label_uses_configured_name_when_known():
    assert_that(league_label("121128"), equal_to("T1 Sweden (121128)"))


def test_league_label_falls_back_to_id_when_unknown():
    assert_that(league_label("999999"), equal_to("League 999999"))


def test_resolve_league_ids_falls_back_to_configured_default():
    expected = [
        lid.strip()
        for lid in FantasyConfig.DEFAULT_AVAILABILITY_LEAGUES.split(",")
        if lid.strip()
    ]
    assert_that(resolve_league_ids(None), equal_to(expected))


def test_resolve_league_ids_splits_and_strips_explicit_arg():
    assert_that(resolve_league_ids(" 1, 2 ,3 "), equal_to(["1", "2", "3"]))


def test_resolve_workers_falls_back_to_configured_default():
    assert_that(
        resolve_workers(None), equal_to(int(FantasyConfig.DEFAULT_AVAILABILITY_WORKERS))
    )


def test_resolve_workers_parses_explicit_value():
    assert_that(resolve_workers("3"), equal_to(3))


def test_resolve_workers_rejects_non_numeric():
    with pytest.raises(InputError):
        resolve_workers("abc")


def test_resolve_workers_rejects_non_positive():
    with pytest.raises(InputError):
        resolve_workers("0")


def test_run_rejects_empty_leagues():
    # An all-blank --leagues resolves to zero leagues; that's a usage error, not
    # a silent success that searches nothing.
    with pytest.raises(InputError):
        Availability().run(
            {"<player>": ["McDavid"], "--leagues": " , ", "--workers": None}
        )


def _row(inner: str) -> str:
    return f"<tr>{inner}</tr>"


def test_ownership_rostered_unescapes_team_name():
    row = _row(
        '<td><a href="/nhl/players/6743">Connor McDavid</a></td>'
        '<td><a href="/hockey/121128/4">North Vancouver &amp; Canucks</a></td>'
    )
    assert_that(ownership(row), equal_to("ROSTERED — North Vancouver & Canucks"))


def test_ownership_free_agent():
    row = _row('<td><a href="/nhl/players/1">A B</a></td><td> FA </td>')
    assert_that(ownership(row), equal_to("FREE AGENT"))


def test_ownership_waivers():
    row = _row('<td><a href="/nhl/players/1">A B</a></td><td> W </td>')
    assert_that(ownership(row), equal_to("WAIVERS"))


def test_ownership_unknown_when_no_markers():
    row = _row('<td><a href="/nhl/players/1">A B</a></td><td></td>')
    assert_that(ownership(row), equal_to("unknown"))


def test_player_regex_extracts_pid_and_name():
    html = '<a href="/nhl/players/8478402" class="x">Connor McDavid</a>'
    match = _PLAYER_RE.search(html)
    assert_that(match.group(1), equal_to("8478402"))
    assert_that(match.group(2), equal_to("Connor McDavid"))


def test_rows_split_into_individual_entries():
    page = (
        '<table>'
        '<tr><a href="/nhl/players/1">One Player</a> FA </tr>'
        '<tr><a href="/nhl/players/2">Two Player</a><a href="/hockey/9/3">Team</a></tr>'
        '</table>'
    )
    rows = _ROW_RE.findall(page)
    owners = [ownership(r) for r in rows]
    assert_that(owners, contains_inanyorder("FREE AGENT", "ROSTERED — Team"))
