"""Opt-in live integration test: read real DailyFaceoff line combinations.

Skipped by default. It fetches live ``line-combinations`` pages from
dailyfaceoff.com (the source this client scrapes), so it only runs when you set
RUN_DAILYFACEOFF_INTEGRATION=1. No secrets or .env required.

Run it with:
    RUN_DAILYFACEOFF_INTEGRATION=1 uv run pytest tests/integration/test_dailyfaceoff_feed.py -v -s

Point it at a different host (e.g. a staging mirror) with:
    DAILYFACEOFF_BASE_URL=https://example.com RUN_DAILYFACEOFF_INTEGRATION=1 ...

To keep the test fast it fetches just two teams by default; override with a
comma-separated DAILYFACEOFF_SLUGS. A stale feed does NOT fail the test (the
client serves last-known lines by design); it only logs a warning, which ``-s``
surfaces.
"""

import os

import pytest

from fantasy_manager.client.news.dailyfaceoff import BASE_URL, DailyFaceoffClient
from fantasy_manager.model.lines import LinesFeed


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DAILYFACEOFF_INTEGRATION") != "1",
    reason="live DailyFaceoff integration test; set "
    "RUN_DAILYFACEOFF_INTEGRATION=1 to run",
)


def test_fetch_lines_end_to_end():
    """Live pages must fetch, extract __NEXT_DATA__, and parse into structure.

    This exercises the real network GET + HTML extraction + parse path, not a
    fixture. It asserts the shape the client promises rather than any particular
    roster, so it stays stable as lines change day to day.
    """
    base_url = os.getenv("DAILYFACEOFF_BASE_URL", BASE_URL)
    slugs = os.getenv("DAILYFACEOFF_SLUGS", "edmonton-oilers,boston-bruins").split(",")
    client = DailyFaceoffClient(base_url=base_url)

    feed = client.fetch_lines(slugs=slugs)

    assert isinstance(feed, LinesFeed)
    assert set(feed.teams) == set(slugs), "expected every requested team to parse"

    for slug in slugs:
        team = feed.teams[slug]
        assert team.team_abbr, f"{slug}: expected a team abbreviation from the page"
        assert (
            team.forward_lines or team.defense_pairs or team.goalies
        ), f"{slug}: expected forwards, defense, or goalies"
