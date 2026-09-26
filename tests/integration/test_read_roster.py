"""Opt-in live integration test: read a real Yahoo roster.

Skipped by default. It hits Yahoo's servers, so it only runs when you set
RUN_YAHOO_INTEGRATION=1 and have the app's secrets configured (YAHOO_COOKIE /
YAHOO_CRUMB and/or YAHOO_CREDS_FILE, e.g. via a local .env).

Run it with:
    RUN_YAHOO_INTEGRATION=1 uv run pytest tests/integration/test_read_roster.py -v -s

Point it at a different league/season with:
    YAHOO_INTEGRATION_LEAGUE=kkupfl FANTASY_SEASON=2026_2027 ...

YAHOO_INTEGRATION_LEAGUE accepts any league name configured for the season —
i.e. a ``<name>.json`` under config/data/season/<FANTASY_SEASON>/league/
(currently: kkupfl, pa). Defaults to kkupfl.
"""
import os

import pytest

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_YAHOO_INTEGRATION") != "1",
    reason="live Yahoo integration test; set RUN_YAHOO_INTEGRATION=1 to run",
)


def test_read_roster_end_to_end():
    """Building the client runs the startup auth self-check; get_team must
    return our team with a non-empty roster over whichever transport is active."""
    league_name = os.getenv("YAHOO_INTEGRATION_LEAGUE", "kkupfl")

    fc = FantasyConfig()
    league = fc.get_league(league_name)
    client = ClientFactory.get_fantasy_client(
        platform=league.platform, league=league, config=fc
    )

    team = client.get_team()

    assert team.roster, "expected a non-empty roster from the read path"
    # The locked players are the auth heuristic used across both transports;
    # if the right team loaded, they should be present.
    rostered_ids = {p.player_id for p in team.roster}
    missing = set(league.locked_players) - rostered_ids
    assert not missing, f"locked players missing from roster: {missing}"
