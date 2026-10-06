#!/usr/bin/env python
"""Check whether players are rostered or available in Yahoo leagues you can view.

Unlike the roster read/write paths, this works against *any* public Yahoo league
— including ones you're not a member of — because it drives the same cookie
transport the app already uses for writes. (The official OAuth API only grants
access to your own leagues, so it can't answer this.)

For each league it POSTs to the league's ``/playersearch`` endpoint (the search
box on the "Players" page) and parses the result rows, reporting each matched
player's ownership: a team name if rostered, ``FA`` if a free agent, or ``W`` if
on waivers.

Usage:
    uv run python scripts/check_player_availability.py "McDavid" "Quinn Hughes"
    uv run python scripts/check_player_availability.py --leagues 121128,121129 "Celebrini"

Options:
    --leagues  Comma-separated Yahoo league IDs. Defaults to the public
               competitive leagues 121128, 121129, 121131.

Requires YAHOO_COOKIE in the environment (or .env) — the same browser-harvested
cookie the write transport uses. A stale/logged-out cookie is reported per league.
"""
import argparse
import html
import re
import sys

import requests

from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.enums.platform_url import PlatformUrl

DEFAULT_LEAGUES = ["121128", "121129", "121131"]

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


def search_league(session: requests.Session, base: str, league_id: str, query: str):
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("players", nargs="+", help="Player name(s) to look up")
    parser.add_argument(
        "--leagues",
        default=",".join(DEFAULT_LEAGUES),
        help="Comma-separated Yahoo league IDs (default: %(default)s)",
    )
    args = parser.parse_args()

    fc = FantasyConfig()
    if not fc.YAHOO_COOKIE:
        print("ERROR: YAHOO_COOKIE is not set (env or .env). Cannot query Yahoo.")
        return 2

    base = fc.get_platform_url(Platform.YAHOO, PlatformUrl.FANTASY_HOCKEY)
    league_ids = [lid.strip() for lid in args.leagues.split(",") if lid.strip()]

    session = requests.Session()
    session.headers.update(
        {"cookie": fc.YAHOO_COOKIE, "user-agent": "Mozilla/5.0"}
    )

    exit_code = 0
    for league_id in league_ids:
        header = f"League {league_id}  ({base}/{league_id}/players)"
        print(f"\n{header}\n" + "=" * len(header))

        for i, query in enumerate(args.players):
            ok, results = search_league(session, base, league_id, query)
            if not ok:
                print("  Could not read league — stale/logged-out cookie? Refresh YAHOO_COOKIE.")
                exit_code = 1
                break
            if not results:
                print(f"  '{query}': no matching players found")
                continue
            for pid, pname, owner in results:
                print(f"  {pname:<24} ({pid:>6})  {owner}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
