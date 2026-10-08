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
from fantasy_manager.exceptions import FantasyAuthError
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.enums.platform_url import PlatformUrl

# The dedicated stdout logger (plain ``%(message)s``); the per-league report is
# data meant for piping/parsing, so it goes to stdout rather than the diagnostic
# stderr logger the CLI framing uses.
STDOUT = logging.getLogger("stdout")

DEFAULT_LEAGUES = "121128,121129,121131"
DEFAULT_WORKERS = 8

# A player link inside a result row: <a href="/nhl/players/6743" ...>Connor McDavid</a>
_PLAYER_RE = re.compile(r"/nhl/players/(\d+)[^>]*>([^<]{2,40})</a>")
# The owner cell links to the fantasy team page: /hockey/<leagueId>/<teamId>">Team Name</a>
_TEAM_RE = re.compile(r"/hockey/\d+/(\d+)\"[^>]*>([^<]{1,60})</a>")
# Free-agent / waiver tokens shown in the owner cell when unrostered.
_FAW_RE = re.compile(r">\s*(FA|W)\b")
_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.S)


def ownership(row: str) -> str:
    """Return the ownership label for a player result row."""
    team = _TEAM_RE.search(row)
    if team:
        return f"ROSTERED — {html.unescape(team.group(2))}"
    faw = _FAW_RE.search(row)
    if faw:
        return "FREE AGENT" if faw.group(1) == "FA" else "WAIVERS"
    return "unknown"


def search_league(
    session: requests.Session, base: str, league_id: str, query: str
) -> tuple[bool, list[tuple[str, str, str]]]:
    """POST the player search for one league; return (ok, [(pid, name, owner)]).

    ``ok`` is False when the league couldn't be read (stale/logged-out cookie).
    """
    resp = session.post(
        f"{base}/{league_id}/playersearch", data={"search": query}, timeout=20
    )
    resp.raise_for_status()
    text = resp.text

    # A dead cookie redirects to a logged-out page with no player rows.
    if "login" in resp.url or "/nhl/players/" not in text:
        return False, []

    results = []
    for row in _ROW_RE.findall(text):
        player = _PLAYER_RE.search(row)
        if not player:
            continue
        results.append(
            (player.group(1), html.unescape(player.group(2)), ownership(row))
        )
    return True, results


class Availability(command.CliCommand):
    """fantasy-manager availability
    Usage:
        fantasy-manager availability [--leagues=<league_ids>] [--workers=<workers>] <player>...

    Options:
        --leagues=<league_ids>  Comma-separated Yahoo league IDs [default: 121128,121129,121131].
        --workers=<workers>     Max concurrent league searches [default: 8]."""

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        """Report ownership of the given player(s) across the given leagues."""
        players = args["<player>"]
        league_ids = [lid.strip() for lid in args["--leagues"].split(",") if lid.strip()]
        workers = int(args["--workers"])

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

        unreadable = False
        for league_id in league_ids:
            header = f"League {league_id}  ({base}/{league_id}/players)"
            STDOUT.info(f"\n{header}\n" + "=" * len(header))

            for qi, query in enumerate(players):
                ok, payload = results[(league_id, qi)]
                if ok is None:
                    STDOUT.info(f"  Could not read league — request failed ({payload}).")
                    unreadable = True
                    break
                if not ok:
                    STDOUT.info(
                        "  Could not read league — stale/logged-out cookie? Refresh YAHOO_COOKIE."
                    )
                    unreadable = True
                    break
                if not payload:
                    STDOUT.info(f"  '{query}': no matching players found")
                    continue
                for pid, pname, owner in payload:
                    STDOUT.info(f"  {pname:<24} ({pid:>6})  {owner}")

        if unreadable:
            return command.error_result(
                FantasyAuthError("One or more leagues could not be read."),
                "One or more leagues could not be read — refresh YAHOO_COOKIE.",
            )
        return command.success_result(
            f"Checked {len(league_ids)} league(s) for {len(players)} player(s)."
        )
