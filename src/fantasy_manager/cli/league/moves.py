"""Report each manager's remaining weekly moves and FAAB for a Yahoo league.

Like ``player availability``, this drives the cookie transport, so it works for
*any* league you can view in a browser — including ones you're not a member of.
(The official OAuth API only exposes your own leagues, so it can't answer this.)

Yahoo only shows the weekly "used N of M adds" counter on *your own* team page,
never on another manager's — so this stitches together three read-only pages to
reconstruct it for everyone:

- ``/<league>/teams``        — the league's team table: each manager's team
                               name, manager name, FAAB ("Waiver Budget"),
                               waiver priority and season move total.
- ``/<league>/settings``     — the "Max Acquisitions per Week" league setting
                               (how many adds each manager gets per week).
- ``/<league>/transactions`` — the transaction log, newest first. We page back
                               through it counting each team's *add*
                               transactions since the start of the fantasy week
                               (Monday, Pacific).

    moves remaining = weekly add limit − adds made since the week started

Knowing how many managers still have moves left (and how much FAAB they hold)
sizes up the waiver competition: if only a couple of managers can still act, a
modest bid is likely to clear; if everyone is flush with moves and budget, you
may need to pay up.
"""

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from fantasy_manager.cli import command
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    FantasyAuthError,
    FantasyManagerError,
    FantasyManagerSoftError,
    InputError,
)
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.util.output import (
    OutputFormat,
    error_payload,
    parse_output_format,
)
from fantasy_manager.util.temporal import (
    PACIFIC_TZ,
    now_pacific,
    start_of_fantasy_week,
)

# The per-manager report is data meant for reading/piping, so it goes to the
# dedicated stdout logger (plain ``%(message)s``) rather than the diagnostic
# stderr logger the CLI framing uses — matching ``player availability``.
STDOUT = logging.getLogger("stdout")

# Version of the structured (``--output json|yaml``) payload shape, emitted as a
# top-level ``version`` field so downstream jq/yq consumers can pin to — and
# branch on — a known schema. Bump it on any backwards-incompatible change
# (renamed/removed fields, changed nesting); additive fields don't require a bump.
# Shared convention with ``player availability`` (see ``util/output``).
SCHEMA_VERSION = 1

# Yahoo's transaction log returns 25 rows at a time, newest first, and pages via
# a ``count`` query param that acts as an *offset* (``count=25`` skips the newest
# 25, ``count=50`` the newest 50, …) — not, despite the name, a page size. We
# step this offset by the page size and walk back until we cross the week
# boundary. 25 × 20 = 500 transactions covers even a frantic week in a deep league.
_TX_PAGE_SIZE = 25
_TX_MAX_PAGES = 20

_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.S)

# --- /teams page --------------------------------------------------------
# A team's own fantasy-page link carries its id and display name:
#   <a ... href="https://.../hockey/121147/11">Nurse Sharks</a>
# The sibling logo link (``.../11"><img ...>``) has no text, so requiring at
# least one non-``<`` char after ``">`` selects the name link. ``[^<]+`` is
# already bounded by the next tag, so we don't cap the length — a longer name
# must not fail the match and silently drop the whole manager's row.
_TEAM_LINK_RE = re.compile(r'/hockey/\d+/(\d+)">([^<]+)</a>')
# The manager's Yahoo profile link; its text is the manager's display name.
# ``[^<]+`` is already bounded by the next tag, so we don't cap the length — a
# longer manager name must still match (an uncapped miss would blank the manager
# field), the same reasoning as the team-name link above.
_MANAGER_RE = re.compile(r'/profile/[^"]+"[^>]*>([^<]+)</a>')
# The numeric/budget cells (Waiver Budget, Waiver Priority, Moves, Trades) all
# carry ``class="Ta-end ..."``; the trailing "Last Activity" cell does not, so
# this selects exactly those four in order.
_END_CELL_RE = re.compile(r'<td class="Ta-end[^"]*"[^>]*>(.*?)</td>', re.S)

# --- /settings page -----------------------------------------------------
# Rendered as ``Max Acquisitions per Week:</td> <td ...> <b>4</b> </td>``. A
# league with no cap renders "No maximum" (no digit), which we treat as None.
_WEEK_LIMIT_RE = re.compile(
    r"Max Acquisitions per Week:?\s*</td>\s*<td[^>]*>\s*(?:<b>\s*)?(\d+)",
    re.S,
)

# --- /transactions page -------------------------------------------------
# Each add is an icon with this title; a combined add/drop row carries one of
# each, so counting this title per row yields the row's add count.
_ADDED_TITLE = 'title="Added Player"'
# The team the transaction belongs to (its id, taken from the team link's href)
# and its timestamp (no year), e.g.
#   <a class="Tst-team-name" href="/hockey/121147/11">Nurse Sharks</a>
#   <span class="... F-timestamp ...">Oct 14, 8:39 pm</span>
# We key adds by the stable team *id* rather than the display name so a team that
# renames itself mid-week still joins to its ``/teams`` row (a name join would
# miss those adds and overstate the manager's remaining moves).
_TX_TEAM_RE = re.compile(r'Tst-team-name"[^>]*/hockey/\d+/(\d+)"')
_TX_TIME_RE = re.compile(r'F-timestamp[^"]*"[^>]*>([^<]+)</span>')


@dataclass
class ManagerRow:
    """One manager's standing columns, scraped from the ``/teams`` table."""

    team_id: str
    team_name: str
    manager: str
    faab: Optional[int]
    waiver_priority: Optional[str]
    season_moves: Optional[str]


def league_name(league_id: str) -> Optional[str]:
    """The configured display name for a league, or ``None`` if unknown.

    Names come from ``AVAILABILITY_LEAGUE_NAMES`` (shared with ``player
    availability``); the scraped pages don't carry them. This is the single
    lookup shared by the human header (:func:`league_label`) and the structured
    payload's ``name`` field.
    """
    return FantasyConfig.AVAILABILITY_LEAGUE_NAMES.get(league_id)


def league_label(league_id: str) -> str:
    """Human label for the report header: ``Name (id)`` when the id is known.

    An id not present in the config map falls back to ``League <id>``.
    """
    name = league_name(league_id)
    return f"{name} ({league_id})" if name else f"League {league_id}"


def parse_team_rows(html_text: str, league_id: str) -> list[ManagerRow]:
    """Parse the ``/teams`` table into one :class:`ManagerRow` per manager.

    Scopes the parse to the table carrying the "Waiver Budget" header so stray
    ``/hockey/<lg>/<id>`` links elsewhere on the page aren't mistaken for team
    rows, and skips rows without a team link (e.g. a co-manager sub-row, which
    renders with blank stat cells).
    """
    idx = html_text.find("Waiver Budget")
    if idx == -1:
        return []
    start = html_text.rfind("<table", 0, idx)
    end = html_text.find("</table>", idx)
    table = html_text[start:end] if start != -1 and end != -1 else html_text[idx:]

    rows: list[ManagerRow] = []
    for row in _ROW_RE.findall(table):
        link = _TEAM_LINK_RE.search(row)
        if not link:
            continue
        team_id = link.group(1)
        team_name = html.unescape(link.group(2)).strip()

        mgr = _MANAGER_RE.search(row)
        manager = html.unescape(mgr.group(1)).strip() if mgr else ""

        # [Waiver Budget, Waiver Priority, Moves, Trades] in column order.
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in _END_CELL_RE.findall(row)]
        faab = None
        if cells:
            digits = re.search(r"\d+", cells[0])
            faab = int(digits.group()) if digits else None
        priority = cells[1] if len(cells) > 1 else None
        season_moves = cells[2] if len(cells) > 2 else None

        rows.append(
            ManagerRow(
                team_id=team_id,
                team_name=team_name,
                manager=manager,
                faab=faab,
                waiver_priority=priority,
                season_moves=season_moves,
            )
        )
    return rows


def parse_weekly_add_limit(html_text: str) -> Optional[int]:
    """Return the "Max Acquisitions per Week" setting, or None when uncapped."""
    match = _WEEK_LIMIT_RE.search(html_text)
    return int(match.group(1)) if match else None


def parse_transaction_datetime(text: str, now: datetime) -> Optional[datetime]:
    """Parse a yearless transaction timestamp (e.g. ``Oct 14, 8:39 pm``).

    The log omits the year, so we assume ``now``'s year and correct for the
    December→January rollover: a date that lands more than a day in the future
    must belong to the previous year. Returns None if the text doesn't parse.
    """
    try:
        parsed = datetime.strptime(text.strip(), "%b %d, %I:%M %p")
    except ValueError:
        return None
    stamped = parsed.replace(year=now.year, tzinfo=PACIFIC_TZ)
    if stamped > now + timedelta(days=1):
        stamped = stamped.replace(year=now.year - 1)
    return stamped


def parse_transaction_adds(
    html_text: str, week_start: datetime, now: datetime
) -> tuple[dict[str, int], bool, bool]:
    """Count add transactions per team on one ``/transactions`` page.

    Returns ``(counts, reached_week_start, had_rows)`` where ``counts`` maps a
    team id to the adds it made on/after ``week_start`` on this page,
    ``reached_week_start`` is True once a transaction older than the week
    boundary is seen (the log is newest-first, so the caller can stop paging),
    and ``had_rows`` is True if the page had any timestamped transaction at all
    (False marks the end of the log).
    """
    counts: dict[str, int] = {}
    reached = False
    had_rows = False
    for row in _ROW_RE.findall(html_text):
        time_match = _TX_TIME_RE.search(row)
        if not time_match:
            continue
        had_rows = True

        n_adds = row.count(_ADDED_TITLE)
        if n_adds == 0:
            continue  # a drop-only (or other) transaction
        team_match = _TX_TEAM_RE.search(row)
        if not team_match:
            continue
        when = parse_transaction_datetime(time_match.group(1), now)
        if when is None:
            continue
        if when < week_start:
            reached = True
            continue
        team_id = team_match.group(1)
        counts[team_id] = counts.get(team_id, 0) + n_adds
    return counts, reached, had_rows


def _fetch(session: requests.Session, url: str) -> requests.Response:
    """GET a Yahoo page, raising for HTTP errors (caller handles the body)."""
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    return resp


def _looks_logged_out(resp: requests.Response) -> bool:
    """Whether the response isn't a normal logged-in Yahoo fantasy page.

    A stale/absent cookie bounces to the login flow (``login`` in the final
    URL). We also treat the absence of a ``logout`` control as logged-out: every
    authenticated fantasy page carries one, so a soft-error or interstitial page
    that returns 200 without bouncing is still caught here rather than being
    parsed as if it were the page we asked for.
    """
    return "login" in resp.url or "logout" not in resp.text


def fetch_team_rows(
    session: requests.Session, base: str, league_id: str
) -> list[ManagerRow]:
    """Read and parse the league's ``/teams`` table over the cookie transport."""
    resp = _fetch(session, f"{base}/{league_id}/teams")
    if _looks_logged_out(resp) or "Waiver Budget" not in resp.text:
        raise FantasyAuthError(
            f"Could not read teams for league {league_id} — stale/logged-out "
            "cookie? Refresh YAHOO_COOKIE."
        )
    return parse_team_rows(resp.text, league_id)


def fetch_weekly_add_limit(
    session: requests.Session, base: str, league_id: str
) -> Optional[int]:
    """Read the weekly add limit from the league ``/settings`` page."""
    resp = _fetch(session, f"{base}/{league_id}/settings")
    # Require the setting's own label, not just a logged-in page: an uncapped
    # league renders "Max Acquisitions per Week: No maximum" (parsed as None),
    # so without this marker a page that merely lacks the setting would be
    # silently misread as uncapped rather than flagged unreadable.
    if _looks_logged_out(resp) or "Max Acquisitions per Week" not in resp.text:
        raise FantasyAuthError(
            f"Could not read settings for league {league_id} — stale/logged-out "
            "cookie? Refresh YAHOO_COOKIE."
        )
    return parse_weekly_add_limit(resp.text)


def fetch_weekly_adds(
    session: requests.Session,
    base: str,
    league_id: str,
    week_start: datetime,
    now: datetime,
) -> dict[str, int]:
    """Count each team's adds since ``week_start`` by paging the transaction log.

    Pages newest-first via the ``count`` offset, stopping as soon as a
    transaction older than the week boundary is seen (or the log runs out), so a
    quiet week costs a single request and only a busy one pages further.

    ``count`` is an absolute offset into a live log, so a transaction added
    between page fetches shifts every later row down one, which can double-count
    or skip a straddling add. The window is milliseconds between sequential
    requests and the effect is at most off-by-one on a team's weekly tally, so we
    accept it rather than snapshot the whole log up front.
    """
    counts: dict[str, int] = {}
    for page in range(_TX_MAX_PAGES):
        url = f"{base}/{league_id}/transactions?count={page * _TX_PAGE_SIZE}"
        resp = _fetch(session, url)
        if _looks_logged_out(resp):
            raise FantasyAuthError(
                f"Could not read transactions for league {league_id} — "
                "stale/logged-out cookie? Refresh YAHOO_COOKIE."
            )
        page_counts, reached, had_rows = parse_transaction_adds(
            resp.text, week_start, now
        )
        for team_id, count in page_counts.items():
            counts[team_id] = counts.get(team_id, 0) + count
        if reached or not had_rows:
            break
    return counts


def moves_left(used: int, limit: Optional[int]) -> str:
    """Format the moves-remaining cell: ``<remaining> of <limit>`` (or uncapped)."""
    if limit is None:
        return f"{used} used (no cap)"
    return f"{max(limit - used, 0)} of {limit}"


def order_managers(
    teams: list[ManagerRow], adds: dict[str, int], limit: Optional[int]
) -> list[ManagerRow]:
    """Sort managers so those most free to act (most moves left, then FAAB) lead.

    With a weekly cap, "most free" means the fewest adds used; uncapped, there's
    no ceiling to subtract from, so fewer adds used still sorts ahead (``-used``).
    Shared by the text report and the structured payload so both agree on order.
    """

    def remaining(team: ManagerRow) -> int:
        used = adds.get(team.team_id, 0)
        return (limit - used) if limit is not None else -used

    return sorted(teams, key=lambda t: (remaining(t), t.faab or 0), reverse=True)


def _error_data(
    err: Exception, league: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Structured payload for a failed run.

    Keeps the top-level shape stable: ``league`` is always present — ``None`` when
    the command failed before reading anything — with a structured ``error``
    object alongside, so a json/yaml consumer reads ``league`` and branches on
    ``error`` the same way regardless of where the failure happened.
    """
    return {
        "version": SCHEMA_VERSION,
        "league": league,
        **error_payload(err),
    }


def _format_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    """Render ``headers`` + ``rows`` as left-aligned, space-padded text lines."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    return [fmt(headers), "  ".join("-" * w for w in widths), *(fmt(r) for r in rows)]


class Moves(command.CliCommand):
    """fantasy-manager league moves

    Show every manager's remaining weekly moves and FAAB for a Yahoo league, so
    you can gauge the waiver competition before placing a bid.

    Usage:
        fantasy-manager league moves --league=<league_id> [--output=<format>]

    Options:
        --league=<league_id>  Yahoo league ID to report on (required).
        -o <format>, --output=<format>
                              Output format: text (default), json, or yaml.
                              json/yaml emit a machine-readable payload on
                              stdout for piping to jq/yq."""

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        """Report every manager's remaining weekly moves and FAAB for a league.

        The ``--output`` format is resolved up front so that an *expected*
        failure (e.g. a missing cookie or an unreadable league) still emits the
        stable ``{"league": ..., "error": {...}}`` payload on stdout for
        json/yaml consumers, rather than an empty stream. A bad ``--output``
        value is intentionally left to propagate: we can't serialize to an
        unknown format, so the runner frames it as plain text. Truly unexpected
        exceptions likewise escape to the runner (no half-built payload).
        """
        output_format = parse_output_format(args.get("--output"))
        try:
            return self._report(args, output_format)
        except FantasyManagerSoftError as err:
            return command.not_permitted_result(
                err, str(err), data=_error_data(err), output_format=output_format
            )
        except FantasyManagerError as err:
            return command.error_result(
                err, str(err), data=_error_data(err), output_format=output_format
            )

    def _report(
        self, args: dict[str, Any], output_format: OutputFormat
    ) -> command.CommandResult:
        """Scrape the three pages, build the result, and (for text) print it."""
        league_id = (args.get("--league") or "").strip()
        if not league_id:
            raise InputError("Pass --league=<league_id> (the Yahoo league ID).")

        fc = FantasyConfig()
        if not fc.YAHOO_COOKIE:
            raise FantasyAuthError(
                "YAHOO_COOKIE is not set (env or .env). Cannot query Yahoo."
            )

        base = fc.get_platform_url(Platform.YAHOO, PlatformUrl.FANTASY_HOCKEY)
        session = requests.Session()
        session.headers.update({"cookie": fc.YAHOO_COOKIE, "user-agent": "Mozilla/5.0"})

        now = now_pacific()
        week_start = start_of_fantasy_week(now)
        try:
            teams = fetch_team_rows(session, base, league_id)
            limit = fetch_weekly_add_limit(session, base, league_id)
            adds = fetch_weekly_adds(session, base, league_id, week_start, now)
        except requests.RequestException as exc:
            return command.error_result(
                exc,
                f"Could not read league {league_id} — request failed ({exc}).",
                data=_error_data(exc),
                output_format=output_format,
            )

        if not teams:
            raise FantasyAuthError(
                f"Could not read teams for league {league_id} — stale/logged-out "
                "cookie? Refresh YAHOO_COOKIE."
            )

        ordered = order_managers(teams, adds, limit)
        if output_format is OutputFormat.TEXT:
            self._print_report(base, league_id, ordered, adds, limit, week_start)
        return command.success_result(
            f"Reported weekly moves and FAAB for {len(teams)} manager(s) "
            f"in league {league_id}.",
            data=self._build_payload(league_id, ordered, adds, limit, week_start),
            output_format=output_format,
        )

    def _build_payload(
        self,
        league_id: str,
        ordered: list[ManagerRow],
        adds: dict[str, int],
        limit: Optional[int],
        week_start: datetime,
    ) -> dict[str, Any]:
        """Build the structured ``--output json|yaml`` payload for the report.

        Managers are listed in the same most-free-to-act-first order as the text
        table, so the two outputs never disagree. ``moves_left`` is ``None`` when
        the league is uncapped (there's no limit to count down from).
        """
        managers = []
        for t in ordered:
            used = adds.get(t.team_id, 0)
            managers.append(
                {
                    "team_id": t.team_id,
                    "team_name": t.team_name,
                    "manager": t.manager or None,
                    "adds_used": used,
                    "moves_left": max(limit - used, 0) if limit is not None else None,
                    "faab": t.faab,
                    "season_moves": t.season_moves,
                    "waiver_priority": t.waiver_priority,
                }
            )
        return {
            "version": SCHEMA_VERSION,
            "league": {
                "id": league_id,
                "name": league_name(league_id),
                "week_start": f"{week_start:%Y-%m-%d}",
                "weekly_add_limit": limit,
                "total_adds_used": sum(adds.get(t.team_id, 0) for t in ordered),
                "managers": managers,
            },
        }

    def _print_report(
        self,
        base: str,
        league_id: str,
        ordered: list[ManagerRow],
        adds: dict[str, int],
        limit: Optional[int],
        week_start: datetime,
    ) -> None:
        """Print the per-manager table, most moves-remaining (then FAAB) first."""
        header = f"{league_label(league_id)}  ({base}/{league_id}/teams)"
        STDOUT.info(f"\n{header}")
        STDOUT.info("=" * len(header))

        total_used = sum(adds.get(t.team_id, 0) for t in ordered)
        cap = f"{limit} adds/manager/week" if limit is not None else "no weekly add cap"
        STDOUT.info(
            f"Week of {week_start:%a %b %d} — {total_used} add(s) used "
            f"leaguewide so far; {cap}\n"
        )

        rows = [
            (
                t.manager or "—",
                t.team_name,
                moves_left(adds.get(t.team_id, 0), limit),
                f"${t.faab}" if t.faab is not None else "—",
                t.season_moves or "—",
                t.waiver_priority or "—",
            )
            for t in ordered
        ]
        headers = (
            "Manager",
            "Team",
            "Moves left",
            "FAAB",
            "Season moves",
            "Waiver pri",
        )
        for line in _format_table(headers, rows):
            STDOUT.info(line)
