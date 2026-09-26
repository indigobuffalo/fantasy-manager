#!/usr/bin/env python
"""Read a fantasy team's roster end-to-end — an integration smoke test.

Builds a real ``YahooClient`` (which runs the startup read-auth self-check:
OAuth probe + cookie check, logging the state of both transports and hard-
failing if neither can read) and calls ``get_team()``, printing the roster it
gets back. This exercises the read-path fallback for real: whichever transport
the probe latches on carries the read, and the cookie scrapers get run against
live Yahoo HTML.

Usage:
    uv run python scripts/read_roster.py [league_name]     # default: kkupfl

Requires the same env/secrets as the app (see .env.example):
  - YAHOO_COOKIE / YAHOO_CRUMB  (cookie transport — needed for the fallback)
  - YAHOO_CREDS_FILE            (OAuth transport)
Set YAHOO_FORCE_COOKIE_READS=1 to skip the OAuth probe and read via cookie.
Set FANTASY_SEASON to pick the league config season (defaults to the app default).
"""
import logging
import sys

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    league_name = sys.argv[1] if len(sys.argv) > 1 else "kkupfl"

    fc = FantasyConfig()
    print(f"\nReading '{league_name}' roster (season {fc.SEASON})\n" + "=" * 50)

    league = fc.get_league(league_name)
    client = ClientFactory.get_fantasy_client(
        platform=league.platform, league=league, config=fc
    )

    # The startup auth self-check already logged which transport is active; this
    # read routes through it (OAuth or cookie fallback).
    team = client.get_team()

    print(f"\nTeam: {team.name}  (team_id={team.team_id}, league={team.league_id})")
    print(f"Roster ({len(team.roster)} players):")
    for p in team.roster:
        positions = ",".join(pos.value for pos in p.eligible_positions)
        print(
            f"  - {p.player_id:>6}  {str(p.name):<24}  "
            f"pos={p.selected_position.value:<4} eligible=[{positions}]"
        )

    if not team.roster:
        print("\nWARNING: roster came back empty — the read path returned no players.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
