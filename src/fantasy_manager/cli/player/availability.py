"""Check whether players are rostered or available in Yahoo leagues you can view.

Unlike the roster read/write paths, this works against *any* public Yahoo league
— including ones you're not a member of — because it drives the same cookie
transport the app already uses for writes. (The official OAuth API only grants
access to your own leagues, so it can't answer this.)

For each league it POSTs to the league's ``/playersearch`` endpoint (the search
box on the "Players" page) and parses the result rows, reporting each matched
player's ownership: a team name if rostered, ``FREE AGENT`` if a free agent, or
``WAIVERS`` if on waivers.

The per-league searches are I/O-bound HTTP round-trips, so they're run
concurrently across a thread pool (see ``--workers``). Output is still printed
per league in the order the leagues were given, so results are deterministic
regardless of which request finishes first.
"""

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from fantasy_manager.cli import command
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    FantasyAuthError,
    FantasyManagerError,
    FantasyManagerSoftError,
    InputError,
)
from fantasy_manager.model.enums.availability_status import AvailabilityStatus
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.util.output import (
    OutputFormat,
    error_payload,
    parse_output_format,
)

# The dedicated stdout logger (plain ``%(message)s``); the per-league report is
# data meant for piping/parsing, so it goes to stdout rather than the diagnostic
# stderr logger the CLI framing uses.
STDOUT = logging.getLogger("stdout")

# A player link inside a result row: <a href="/nhl/players/6743" ...>Connor McDavid</a>
_PLAYER_RE = re.compile(r"/nhl/players/(\d+)[^>]*>([^<]{2,40})</a>")
# The owner cell links to the fantasy team page: /hockey/<leagueId>/<teamId>">Team Name</a>
_TEAM_RE = re.compile(r"/hockey/\d+/(\d+)\"[^>]*>([^<]{1,60})</a>")
# Free-agent / waiver tokens shown in the owner cell when unrostered. The owner
# cell renders the token in a bare ``<div>`` — ``FA`` for a free agent, ``W (<date>)``
# for a player on waivers. We anchor to ``<div ...>`` (not just ``>``) so we skip the
# *game-result* link earlier in the row (``<a ...>W, 4-0 vs FLA</a>`` — a win), which
# would otherwise be misread as a waiver "W". The ``\b`` keeps a three-letter opponent
# abbreviation (e.g. ``<div>WPG</div>``) from matching the "W" either.
_FAW_RE = re.compile(r"<div[^>]*>\s*(FA|W)\b")
_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.S)


def resolve_league_ids(leagues_arg: str | None) -> list[str]:
    """Parse the ``--leagues`` CSV into IDs, falling back to the configured default.

    When ``--leagues`` isn't given, use ``DEFAULT_AVAILABILITY_LEAGUES`` from
    config (env-overridable) rather than a value hard-coded in the usage string.
    """
    raw = leagues_arg or FantasyConfig.DEFAULT_AVAILABILITY_LEAGUES
    return [lid.strip() for lid in raw.split(",") if lid.strip()]


def resolve_workers(workers_arg: str | None) -> int:
    """Parse ``--workers`` into a positive int, falling back to the configured default.

    Like ``--leagues``, the default lives in config (``DEFAULT_AVAILABILITY_WORKERS``)
    rather than the usage string. A non-numeric or non-positive value is a user error,
    surfaced as a clean ``InputError`` instead of a raw ``ValueError`` from ``int()``.
    """
    raw = (
        workers_arg
        if workers_arg is not None
        else FantasyConfig.DEFAULT_AVAILABILITY_WORKERS
    )
    try:
        workers = int(raw)
    except (TypeError, ValueError):
        raise InputError(f"--workers must be an integer, got '{raw}'.")
    if workers < 1:
        raise InputError(f"--workers must be at least 1, got {workers}.")
    return workers


def league_name(league_id: str) -> str | None:
    """The configured display name for a league, or ``None`` if unknown.

    Names come from config (the ``/playersearch`` response doesn't carry them),
    so an ID passed via ``--leagues`` that isn't in the map has no name. This is
    the single lookup shared by the human header (:func:`league_label`) and the
    structured payload's ``name`` field.
    """
    return FantasyConfig.AVAILABILITY_LEAGUE_NAMES.get(league_id)


def league_label(league_id: str) -> str:
    """Human label for a league header: ``Name (id)`` when known, else ``League id``.

    An ID passed via ``--leagues`` that isn't in the config map falls back to the ID.
    """
    name = league_name(league_id)
    return f"{name} ({league_id})" if name else f"League {league_id}"


def ownership(row: str) -> tuple[AvailabilityStatus, str | None]:
    """Return the ``(status, owner)`` for a player result row.

    ``owner`` is the team name only when the player is ``ROSTERED``; it's ``None``
    for free agents, waivers, and unparseable ownership cells.
    """
    team = _TEAM_RE.search(row)
    if team:
        return AvailabilityStatus.ROSTERED, html.unescape(team.group(2))
    faw = _FAW_RE.search(row)
    if faw:
        if faw.group(1) == "FA":
            return AvailabilityStatus.FREE_AGENT, None
        return AvailabilityStatus.WAIVERS, None
    return AvailabilityStatus.UNKNOWN, None


def ownership_label(status: AvailabilityStatus, owner: str | None) -> str:
    """Human-readable ownership label for the ``text`` output's per-player row."""
    if status is AvailabilityStatus.ROSTERED:
        return f"ROSTERED — {owner}"
    if status is AvailabilityStatus.FREE_AGENT:
        return "FREE AGENT"
    if status is AvailabilityStatus.WAIVERS:
        return "WAIVERS"
    return "unknown"


def _player_entry(
    query: str,
    status: AvailabilityStatus,
    *,
    name: str | None = None,
    pid: str | None = None,
    owner: str | None = None,
) -> dict[str, Any]:
    """One row of a league's structured ``players`` list.

    ``name``/``pid``/``owner`` are ``None`` for the ``NO_MATCH`` status, which
    doesn't correspond to a matched player. ``status`` is serialized as its
    stable string value.
    """
    return {
        "query": query,
        "name": name,
        "pid": pid,
        "status": status.value,
        "owner": owner,
    }


def search_league(
    session: requests.Session, base: str, league_id: str, query: str
) -> tuple[bool, list[tuple[str, str, AvailabilityStatus, str | None]]]:
    """POST the player search for one league; return (ok, [(pid, name, status, owner)]).

    ``ok`` is False when the league couldn't be read (stale/logged-out cookie).
    """
    resp = session.post(
        f"{base}/{league_id}/playersearch", data={"search": query}, timeout=20
    )
    resp.raise_for_status()
    text = resp.text

    # A dead/logged-out cookie bounces to the Yahoo login page; a live search —
    # even one that matches zero players — always lands back on this league's
    # playersearch page with the search form present. Key off those (not the
    # presence of player rows) so a simple typo returns "no matches" rather than
    # being misreported as a stale cookie.
    if (
        "login" in resp.url
        or f"/hockey/{league_id}/" not in resp.url
        or 'name="search"' not in text
    ):
        return False, []

    results = []
    for row in _ROW_RE.findall(text):
        player = _PLAYER_RE.search(row)
        if not player:
            continue
        status, owner = ownership(row)
        results.append((player.group(1), html.unescape(player.group(2)), status, owner))
    return True, results


class Availability(command.CliCommand):
    """fantasy-manager player availability
    Usage:
        fantasy-manager player availability [--leagues=<league_ids>] [--workers=<workers>] [--output=<format>] <player>...

    Options:
        --leagues=<league_ids>  Comma-separated Yahoo league IDs. Defaults to the
                                configured DEFAULT_AVAILABILITY_LEAGUES.
        --workers=<workers>     Max concurrent league searches. Defaults to the
                                configured DEFAULT_AVAILABILITY_WORKERS.
        -o <format>, --output=<format>
                                Output format: text (default), json, or yaml.
                                json/yaml emit a machine-readable payload on
                                stdout for piping to jq/yq."""

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        """Report ownership of the given player(s) across the given leagues.

        The ``--output`` format is resolved up front so that an *expected*
        failure (e.g. a missing cookie) still emits a structured
        ``{"error": {...}}`` object on stdout for json/yaml consumers, rather
        than an empty stream. A bad ``--output`` value is intentionally left to
        propagate: we can't serialize to an unknown format, so the runner frames
        it as plain text. Truly unexpected exceptions likewise escape to the
        runner, which reports them as plain text (no half-built payload).
        """
        output_format = parse_output_format(args.get("--output"))
        try:
            return self._report(args, output_format)
        except FantasyManagerSoftError as err:
            return command.not_permitted_result(
                err, str(err), data=error_payload(err), output_format=output_format
            )
        except FantasyManagerError as err:
            return command.error_result(
                err, str(err), data=error_payload(err), output_format=output_format
            )

    def _report(
        self, args: dict[str, Any], output_format: OutputFormat
    ) -> command.CommandResult:
        """Do the ownership lookup and build the result for ``output_format``."""
        players = args["<player>"]
        league_ids = resolve_league_ids(args["--leagues"])
        if not league_ids:
            raise InputError(
                "No leagues to search — pass --leagues or configure "
                "DEFAULT_AVAILABILITY_LEAGUES."
            )
        workers = resolve_workers(args["--workers"])

        fc = FantasyConfig()
        if not fc.YAHOO_COOKIE:
            raise FantasyAuthError(
                "YAHOO_COOKIE is not set (env or .env). Cannot query Yahoo."
            )

        base = fc.get_platform_url(Platform.YAHOO, PlatformUrl.FANTASY_HOCKEY)

        session = requests.Session()
        session.headers.update({"cookie": fc.YAHOO_COOKIE, "user-agent": "Mozilla/5.0"})

        # Fan out every (league, query) search across a thread pool. A shared
        # Session is fine here: we only send requests (never mutate it), and its
        # underlying urllib3 connection pool is thread-safe. Results are keyed by
        # (league_id, query_index) so printing stays deterministic below.
        def run_search(league_id: str, query: str):
            try:
                return search_league(session, base, league_id, query)
            except requests.RequestException as exc:
                return None, exc  # None => the request itself failed

        tasks = [
            (league_id, qi, query)
            for league_id in league_ids
            for qi, query in enumerate(players)
        ]
        results: dict[tuple[str, int], tuple] = {}
        if tasks:
            with ThreadPoolExecutor(
                max_workers=max(1, min(workers, len(tasks)))
            ) as pool:
                futures = {
                    pool.submit(run_search, league_id, query): (league_id, qi)
                    for league_id, qi, query in tasks
                }
                for future, key in futures.items():
                    results[key] = future.result()

        # Build the structured payload in league/query order while (for the text
        # format) emitting the same human-readable report as before. json/yaml
        # consumers get the payload from the runner; text consumers see the
        # per-league log lines on stdout.
        is_text = output_format is OutputFormat.TEXT
        unreadable = False
        leagues_data = []
        for league_id in league_ids:
            if is_text:
                header = f"{league_label(league_id)}  ({base}/{league_id}/players)"
                STDOUT.info(f"\n{header}\n" + "=" * len(header))

            readable = True
            players_data = []
            for qi, query in enumerate(players):
                ok, payload = results[(league_id, qi)]
                if not ok:
                    # ``ok is None`` => the request itself failed (payload is the
                    # exception); ``not ok`` => a stale/logged-out cookie. Either
                    # way the whole league is unreadable — flag it at the league
                    # level (not against any one query) and stop searching it.
                    readable = False
                    unreadable = True
                    if is_text:
                        if ok is None:
                            STDOUT.info(
                                f"  Could not read league — request failed ({payload})."
                            )
                        else:
                            STDOUT.info(
                                "  Could not read league — stale/logged-out cookie? Refresh YAHOO_COOKIE."
                            )
                    break
                if not payload:
                    players_data.append(
                        _player_entry(query, AvailabilityStatus.NO_MATCH)
                    )
                    if is_text:
                        STDOUT.info(f"  '{query}': no matching players found")
                    continue
                for pid, pname, status, owner in payload:
                    players_data.append(
                        _player_entry(query, status, name=pname, pid=pid, owner=owner)
                    )
                    if is_text:
                        STDOUT.info(
                            f"  {pname:<24} ({pid:>6})  {ownership_label(status, owner)}"
                        )

            leagues_data.append(
                {
                    "id": league_id,
                    "name": league_name(league_id),
                    "readable": readable,
                    "players": players_data,
                }
            )

        data = {"leagues": leagues_data}
        if unreadable:
            return command.error_result(
                FantasyAuthError("One or more leagues could not be read."),
                "One or more leagues could not be read — refresh YAHOO_COOKIE.",
                data=data,
                output_format=output_format,
            )
        return command.success_result(
            f"Checked {len(league_ids)} league(s) for {len(players)} player(s).",
            data=data,
            output_format=output_format,
        )
