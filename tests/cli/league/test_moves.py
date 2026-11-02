"""Unit tests for the ``league moves`` scrapers and formatting.

Fixtures mirror the real Yahoo markup (captured live from league 121147) closely
enough to exercise the regexes, but stay offline — no HTTP is made.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from hamcrest import assert_that, equal_to, is_, none

import fantasy_manager.cli.league.moves as moves_module
from fantasy_manager.cli.league.moves import (
    ManagerRow,
    Moves,
    league_label,
    moves_left,
    parse_team_rows,
    parse_transaction_adds,
    parse_transaction_datetime,
    parse_weekly_add_limit,
)
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.util.output import OutputFormat
from fantasy_manager.util.temporal import start_of_fantasy_week

PACIFIC = ZoneInfo("America/Los_Angeles")

# A trimmed ``/teams`` table: header row, two real team rows, and a co-manager
# sub-row (no team link, blank stats) that must be skipped.
TEAMS_HTML = """
<table>
<tr><th>Team Name</th><th>Manager</th><th>Email</th>
<th class="Ta-end Phone-hidden">Waiver Budget</th>
<th class="Ta-end Phone-hidden">Waiver Priority</th>
<th class="Ta-end Phone-hidden">Moves</th>
<th class="Ta-end Phone-hidden">Trades</th>
<th class="Phone-hidden">Last League Activity</th></tr>
<tr class="team-11"><td><a class="Grid-u" href="/hockey/121147/11"><img alt="logo"> </a><a href="https://hockey.fantasysports.yahoo.com/hockey/121147/11">Nurse Sharks</a></td>
<td><span class="user-id"><a href="https://profiles.sports.yahoo.com/profile/stephen111012" target="sports">Stephen</a></span></td>
<td><a href="/hockey/121147/emailleague?mids[]=12">stephen.akerson@gmail.com</a></td>
<td class="Ta-end Phone-hidden">$96</td><td class="Ta-end Phone-hidden">3</td>
<td class="Ta-end Phone-hidden">17</td> <td class="Ta-end Phone-hidden">0</td>
<td class="Phone-hidden">Fri Oct 16 10:03am PDT</td> </tr>
<tr class="team-3"><td><a class="Grid-u" href="/hockey/121147/3"><img alt="logo"> </a><a href="https://hockey.fantasysports.yahoo.com/hockey/121147/3">Beers United</a></td>
<td><span class="user-id"><a href="https://profiles.sports.yahoo.com/profile/marek91" target="sports">Marek</a></span></td>
<td><a href="/hockey/121147/emailleague?mids[]=4">m.beny91@seznam.cz</a></td>
<td class="Ta-end Phone-hidden">$72</td><td class="Ta-end Phone-hidden">2</td>
<td class="Ta-end Phone-hidden">11</td> <td class="Ta-end Phone-hidden">0</td>
<td class="Phone-hidden">Fri Oct 16 12:03am PDT</td> </tr>
<tr><td>Co-Manager</td><td><span class="user-id">A Commish Commissioner</span></td>
<td>commish@kkupfl.com</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>
</table>
"""

SETTINGS_HTML = (
    '<tr><td class="typeStandard">Max Acquisitions per Week:</td> \n'
    ' <td width="410" class="typeStandard">\n  <b>4</b>\n </td></tr>'
)

SETTINGS_HTML_UNCAPPED = (
    '<tr><td class="typeStandard">Max Acquisitions per Week:</td>'
    ' <td class="typeStandard">No maximum</td></tr>'
)


def _tx_row(
    team: str, when: str, *, team_id: str, added: int, dropped: int = 0
) -> str:
    icons = "".join(
        '<span class="F-icon" title="Added Player">&#xe035;</span>'
        for _ in range(added)
    ) + "".join(
        '<span class="F-icon" title="Dropped Player">&#xe033;</span>'
        for _ in range(dropped)
    )
    return (
        "<tr>"
        f'<td class="Ta-c">{icons}</td>'
        '<td colspan="2"><a href="/nhl/players/1">A Player</a></td>'
        '<td class="Ta-end"><span class="Grid-u">'
        f'<a class="Tst-team-name" href="/hockey/121147/{team_id}">{team}</a>'
        f'<span class="Block F-timestamp Fz-xxs Nowrap">{when}</span>'
        "</span></td></tr>"
    )


def test_league_label_known_and_unknown():
    assert_that(league_label("121147"), equal_to("T2 San Jose (121147)"))
    assert_that(league_label("999999"), equal_to("League 999999"))


def test_parse_team_rows_extracts_columns_and_skips_co_manager():
    rows = parse_team_rows(TEAMS_HTML, "121147")
    assert_that(len(rows), equal_to(2))

    sharks = rows[0]
    assert_that(sharks.team_id, equal_to("11"))
    assert_that(sharks.team_name, equal_to("Nurse Sharks"))
    assert_that(sharks.manager, equal_to("Stephen"))
    assert_that(sharks.faab, equal_to(96))
    assert_that(sharks.waiver_priority, equal_to("3"))
    assert_that(sharks.season_moves, equal_to("17"))

    assert_that(rows[1].team_name, equal_to("Beers United"))
    assert_that(rows[1].faab, equal_to(72))


def test_parse_weekly_add_limit_reads_bold_number():
    assert_that(parse_weekly_add_limit(SETTINGS_HTML), equal_to(4))


def test_parse_weekly_add_limit_none_when_uncapped():
    assert_that(parse_weekly_add_limit(SETTINGS_HTML_UNCAPPED), is_(none()))


def test_parse_transaction_datetime_assumes_current_year():
    now = datetime(2026, 10, 16, 9, 0, tzinfo=PACIFIC)
    parsed = parse_transaction_datetime("Oct 14, 8:39 pm", now)
    assert_that(parsed, equal_to(datetime(2026, 10, 14, 20, 39, tzinfo=PACIFIC)))


def test_parse_transaction_datetime_rolls_back_across_new_year():
    # Reading a late-December transaction in early January: it's last year's.
    now = datetime(2027, 1, 2, 9, 0, tzinfo=PACIFIC)
    parsed = parse_transaction_datetime("Dec 30, 11:00 pm", now)
    assert_that(parsed, equal_to(datetime(2026, 12, 30, 23, 0, tzinfo=PACIFIC)))


def test_parse_transaction_datetime_invalid_returns_none():
    now = datetime(2026, 10, 16, 9, 0, tzinfo=PACIFIC)
    assert_that(parse_transaction_datetime("not a date", now), is_(none()))


def test_parse_transaction_adds_counts_adds_since_week_start():
    now = datetime(2026, 10, 16, 9, 0, tzinfo=PACIFIC)
    week_start = datetime(2026, 10, 13, 0, 0, tzinfo=PACIFIC)
    page = (
        _tx_row("Nurse Sharks", "Oct 14, 8:39 pm", team_id="11", added=1)
        + _tx_row("Beers United", "Oct 15, 3:45 pm", team_id="3", added=1, dropped=1)
        + _tx_row("Beers United", "Oct 14, 7:07 am", team_id="3", added=1)
        + _tx_row("Pasta Party", "Oct 13, 6:00 am", team_id="5", added=1, dropped=0)
        # drop-only (no add) — ignored
        + _tx_row("Pasta Party", "Oct 14, 1:00 pm", team_id="5", added=0, dropped=1)
        # before the week boundary — not counted, trips ``reached``
        + _tx_row("Nurse Sharks", "Oct 12, 8:00 am", team_id="11", added=1)
    )
    counts, reached, had_rows = parse_transaction_adds(page, week_start, now)
    assert_that(had_rows, is_(True))
    assert_that(reached, is_(True))
    # Keyed by team id, so a mid-week rename can't orphan a team's adds.
    assert_that(counts.get("11"), equal_to(1))
    assert_that(counts.get("3"), equal_to(2))
    assert_that(counts.get("5"), equal_to(1))


def test_parse_transaction_adds_empty_page():
    now = datetime(2026, 10, 16, 9, 0, tzinfo=PACIFIC)
    week_start = datetime(2026, 10, 13, 0, 0, tzinfo=PACIFIC)
    counts, reached, had_rows = parse_transaction_adds(
        "<table></table>", week_start, now
    )
    assert_that(counts, equal_to({}))
    assert_that(reached, is_(False))
    assert_that(had_rows, is_(False))


def test_moves_left_capped_and_uncapped():
    assert_that(moves_left(2, 4), equal_to("2 of 4"))
    assert_that(moves_left(5, 4), equal_to("0 of 4"))  # never negative
    assert_that(moves_left(3, None), equal_to("3 used (no cap)"))


@freeze_time("2026-10-16 18:00:00")  # Friday; week started Mon Oct 12 Pacific
def test_start_of_fantasy_week_is_monday_pacific():
    start = start_of_fantasy_week()
    assert_that((start.year, start.month, start.day), equal_to((2026, 10, 12)))
    assert_that((start.hour, start.minute), equal_to((0, 0)))


def test_run_rejects_missing_league():
    # A missing --league is a usage error surfaced as a failed result (so a
    # --output consumer still gets a structured error) rather than a raised
    # exception — text mode still exits non-zero either way.
    result = Moves().run({"--league": None})
    assert_that(result.return_code, equal_to(1))
    assert_that(result.data["league"], is_(none()))
    assert_that(result.data["error"]["type"], equal_to("InputError"))


def _run_moves(monkeypatch, argv, teams, limit, adds):
    """Drive ``Moves`` end-to-end with the three page scrapes stubbed out.

    ``argv`` is parsed by the command's own docopt usage (so option spellings are
    exercised exactly as the real CLI would see them), and the ``fetch_*``
    helpers are replaced with canned returns so ``run`` does no I/O.
    """
    monkeypatch.setattr(FantasyConfig, "YAHOO_COOKIE", "fake-cookie")
    monkeypatch.setattr(moves_module, "fetch_team_rows", lambda *a, **k: teams)
    monkeypatch.setattr(moves_module, "fetch_weekly_add_limit", lambda *a, **k: limit)
    monkeypatch.setattr(moves_module, "fetch_weekly_adds", lambda *a, **k: adds)
    command = Moves()
    args = command.parse_args(["league", "moves"] + argv)
    return command.run(args)


@freeze_time("2026-10-16 18:00:00")  # Friday; week started Mon Oct 12 Pacific
def test_run_threads_output_format_and_data_for_json(monkeypatch):
    teams = [
        ManagerRow("11", "Nurse Sharks", "Stephen", 96, "3", "17"),
        ManagerRow("3", "Beers United", "Marek", 72, "2", "11"),
    ]
    result = _run_moves(
        monkeypatch,
        ["--league=121147", "--output", "json"],
        teams=teams,
        limit=4,
        adds={"11": 1, "3": 3},  # keyed by team id
    )
    assert_that(result.return_code, equal_to(0))
    assert_that(result.output_format, equal_to(OutputFormat.JSON))
    assert_that(
        result.data,
        equal_to(
            {
                "version": 1,
                "league": {
                    "id": "121147",
                    "name": "T2 San Jose",
                    "week_start": "2026-10-12",
                    "weekly_add_limit": 4,
                    "total_adds_used": 4,
                    # Ordered most-free-to-act first: Sharks (3 left) before
                    # Beers (1 left), matching the text table.
                    "managers": [
                        {
                            "team_id": "11",
                            "team_name": "Nurse Sharks",
                            "manager": "Stephen",
                            "adds_used": 1,
                            "moves_left": 3,
                            "faab": 96,
                            "season_moves": "17",
                            "waiver_priority": "3",
                        },
                        {
                            "team_id": "3",
                            "team_name": "Beers United",
                            "manager": "Marek",
                            "adds_used": 3,
                            "moves_left": 1,
                            "faab": 72,
                            "season_moves": "11",
                            "waiver_priority": "2",
                        },
                    ],
                },
            }
        ),
    )


@freeze_time("2026-10-16 18:00:00")
def test_run_uncapped_league_reports_null_moves_left(monkeypatch):
    # An uncapped league has no weekly ceiling, so ``moves_left`` is null and the
    # limit is null rather than a number.
    result = _run_moves(
        monkeypatch,
        ["--league=121147", "--output", "json"],
        teams=[ManagerRow("11", "Nurse Sharks", "Stephen", 96, "3", "17")],
        limit=None,
        adds={"11": 2},  # keyed by team id
    )
    assert_that(result.data["league"]["weekly_add_limit"], is_(none()))
    assert_that(result.data["league"]["managers"][0]["moves_left"], is_(none()))
    assert_that(result.data["league"]["managers"][0]["adds_used"], equal_to(2))


def test_run_emits_structured_error_when_cookie_missing(monkeypatch):
    # An expected failure (no cookie) still yields the stable payload shape —
    # ``league`` null plus a structured ``error`` — for json/yaml consumers.
    monkeypatch.setattr(FantasyConfig, "YAHOO_COOKIE", "")
    command = Moves()
    args = command.parse_args(
        ["league", "moves", "--league=121147", "--output", "json"]
    )
    result = command.run(args)
    assert_that(result.return_code, equal_to(1))
    assert_that(result.output_format, equal_to(OutputFormat.JSON))
    assert_that(result.data["league"], is_(none()))
    assert_that(result.data["error"]["type"], equal_to("FantasyAuthError"))
