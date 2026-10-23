import pytest
from hamcrest import assert_that, equal_to, contains_inanyorder

import fantasy_manager.cli.player.availability as availability_module
from fantasy_manager.cli.player.availability import (
    _PLAYER_RE,
    _ROW_RE,
    Availability,
    league_label,
    ownership,
    ownership_label,
    resolve_league_ids,
    resolve_workers,
)
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import InputError
from fantasy_manager.model.enums.availability_status import AvailabilityStatus
from fantasy_manager.util.output import OutputFormat


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
    assert_that(
        ownership(row),
        equal_to((AvailabilityStatus.ROSTERED, "North Vancouver & Canucks")),
    )


# A minimal stand-in for Yahoo's player cell: the name link plus the
# "ysf-player-detail" game-result link. ``last_game`` is the most recent result
# text ("W, 4-0 vs FLA" for a win) rendered inside an <a>, which must NOT be read
# as the owner cell.
def _player_cell(last_game: str = "") -> str:
    detail = (
        f'<div class="ysf-player-detail"><span class="ysf-game-status">'
        f'<a href="https://sports.yahoo.com/nhl/game">{last_game}</a></span></div>'
        if last_game
        else ""
    )
    return f'<td><a href="/nhl/players/1">A B</a>{detail}</td>'


# The owner cell as Yahoo renders it: a bare <div> holding the token.
def _owner_cell(token: str) -> str:
    return f'<td><div style="overflow: hidden;">{token}</div></td>'


def test_ownership_free_agent():
    row = _row(_player_cell() + _owner_cell("FA"))
    assert_that(ownership(row), equal_to((AvailabilityStatus.FREE_AGENT, None)))


def test_ownership_waivers_with_clear_date():
    # On waivers Yahoo shows "W (<date>)", not a bare "W".
    row = _row(_player_cell() + _owner_cell("W (Oct 23)"))
    assert_that(ownership(row), equal_to((AvailabilityStatus.WAIVERS, None)))


def test_ownership_free_agent_ignores_winning_game_result():
    # Regression: a free agent whose last game was a win ("W, 4-0 vs FLA") must
    # still read as FREE AGENT — the leading "W" of the game result previously
    # got mistaken for a waiver "W".
    row = _row(_player_cell("W, 4-0 vs FLA") + _owner_cell("FA"))
    assert_that(ownership(row), equal_to((AvailabilityStatus.FREE_AGENT, None)))


def test_ownership_waivers_ignores_winning_game_result():
    row = _row(_player_cell("W, 4-0 vs FLA") + _owner_cell("W (Oct 23)"))
    assert_that(ownership(row), equal_to((AvailabilityStatus.WAIVERS, None)))


def test_ownership_free_agent_ignores_w_opponent_abbreviation():
    # An opponent cell like "WPG" sits before the owner cell; its "W" must not
    # be read as a waiver marker.
    row = _row(_player_cell() + "<td><div>WPG</div></td>" + _owner_cell("FA"))
    assert_that(ownership(row), equal_to((AvailabilityStatus.FREE_AGENT, None)))


def test_ownership_unknown_when_no_markers():
    row = _row(_player_cell() + "<td><div></div></td>")
    assert_that(ownership(row), equal_to((AvailabilityStatus.UNKNOWN, None)))


def test_ownership_label_renders_text_for_each_status():
    assert_that(
        ownership_label(AvailabilityStatus.ROSTERED, "Team X"),
        equal_to("ROSTERED — Team X"),
    )
    assert_that(
        ownership_label(AvailabilityStatus.FREE_AGENT, None), equal_to("FREE AGENT")
    )
    assert_that(ownership_label(AvailabilityStatus.WAIVERS, None), equal_to("WAIVERS"))
    assert_that(ownership_label(AvailabilityStatus.UNKNOWN, None), equal_to("unknown"))


def test_player_regex_extracts_pid_and_name():
    html = '<a href="/nhl/players/8478402" class="x">Connor McDavid</a>'
    match = _PLAYER_RE.search(html)
    assert_that(match.group(1), equal_to("8478402"))
    assert_that(match.group(2), equal_to("Connor McDavid"))


def test_rows_split_into_individual_entries():
    page = (
        "<table>"
        '<tr><a href="/nhl/players/1">One Player</a><td><div>FA</div></td></tr>'
        '<tr><a href="/nhl/players/2">Two Player</a><a href="/hockey/9/3">Team</a></tr>'
        "</table>"
    )
    rows = _ROW_RE.findall(page)
    owners = [ownership(r) for r in rows]
    assert_that(
        owners,
        contains_inanyorder(
            (AvailabilityStatus.FREE_AGENT, None),
            (AvailabilityStatus.ROSTERED, "Team"),
        ),
    )


def _run_with_fake_search(monkeypatch, argv, payload):
    """Drive ``Availability`` end-to-end with the network search stubbed out.

    ``argv`` is parsed by the command's own docopt usage (so option spellings
    are exercised exactly as the real CLI would see them), and ``search_league``
    is replaced with a canned ``(ok, payload)`` so ``run`` does no I/O.
    """
    monkeypatch.setattr(FantasyConfig, "YAHOO_COOKIE", "fake-cookie")
    monkeypatch.setattr(
        availability_module,
        "search_league",
        lambda session, base, league_id, query: (True, payload),
    )
    command = Availability()
    args = command.parse_args(["player", "availability"] + argv)
    return command.run(args)


def test_run_threads_output_format_and_data_for_json(monkeypatch):
    result = _run_with_fake_search(
        monkeypatch,
        ["--leagues=9", "--output", "json", "McDavid"],
        [("6743", "Connor McDavid", AvailabilityStatus.FREE_AGENT, None)],
    )
    assert_that(result.return_code, equal_to(0))
    assert_that(result.output_format, equal_to(OutputFormat.JSON))
    assert_that(
        result.data,
        equal_to(
            {
                "leagues": [
                    {
                        "id": "9",
                        "name": None,
                        "players": [
                            {
                                "query": "McDavid",
                                "name": "Connor McDavid",
                                "pid": "6743",
                                "status": "FREE_AGENT",
                                "owner": None,
                            }
                        ],
                    }
                ]
            }
        ),
    )


def test_run_honors_abbreviated_output_flag(monkeypatch):
    # docopt accepts the unambiguous long-option prefix ``--out`` for
    # ``--output``; the resolved format must still reach the result (a prior
    # top-level argv scan missed ``--out`` and silently produced no output).
    result = _run_with_fake_search(
        monkeypatch,
        ["--leagues=9", "--out", "json", "McDavid"],
        [("6743", "Connor McDavid", AvailabilityStatus.FREE_AGENT, None)],
    )
    assert_that(result.output_format, equal_to(OutputFormat.JSON))


def test_run_defaults_to_text_format(monkeypatch):
    result = _run_with_fake_search(
        monkeypatch,
        ["--leagues=9", "McDavid"],
        [("6743", "Connor McDavid", AvailabilityStatus.FREE_AGENT, None)],
    )
    assert_that(result.output_format, equal_to(OutputFormat.TEXT))
