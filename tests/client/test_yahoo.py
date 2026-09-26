from unittest.mock import Mock, patch

import pytest

from conftest import *
from fantasy_manager.client.yahoo import (
    ALREADY_PLAYED_MARKER,
    WAIVER_CLAIM_PLACED_MARKER,
    WEEKLY_LIMIT_MARKER,
    YahooClient,
)
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    AlreadyPlayedError,
    FantasyAuthError,
    MaxAddsError,
    UnintendedWaiverAddError,
)


CRUMB = "test-crumb"
TEAM_URL = "https://hockey.fantasysports.yahoo.com/hockey/123/1"


@pytest.fixture
def yahoo_client(mock_league):
    """A YahooClient whose transports are stubbed out.

    ``_refresh_context`` is patched so construction touches neither OAuth nor
    the network; the cookie write transport is then replaced with a mock so the
    scaffolding helpers can be exercised in isolation.
    """
    config = Mock(spec=FantasyConfig)
    config.YAHOO_COOKIE = "cookie-header"
    config.YAHOO_CRUMB = CRUMB
    config.get_platform_url = Mock(
        return_value="https://hockey.fantasysports.yahoo.com/hockey"
    )
    with patch.object(YahooClient, "_refresh_context"):
        client = YahooClient(league=mock_league, config=config)
    client.crumb = CRUMB
    client.write_session = Mock()
    yield client


def _response(text: str) -> Mock:
    resp = Mock()
    resp.text = text
    return resp


def test_check_cookie_auth_passes_when_locked_players_present(yahoo_client):
    # mock_league.locked_players == (1, 2, 3)
    yahoo_client.write_session.get.return_value = _response(
        "roster contains 1, 2 and 3"
    )
    yahoo_client._check_cookie_auth()
    yahoo_client.write_session.get.assert_called_once_with(TEAM_URL)


def test_check_cookie_auth_raises_on_stale_cookie(yahoo_client):
    yahoo_client.write_session.get.return_value = _response("logged out; only 1 and 2")
    with pytest.raises(FantasyAuthError):
        yahoo_client._check_cookie_auth()


def test_post_write_injects_crumb_and_returns_response(yahoo_client):
    resp = _response("all good, player added")
    yahoo_client.write_session.post.return_value = resp

    result = yahoo_client._post_write("addplayer", {"apid": 6751, "stat1": "P"})

    assert result is resp
    yahoo_client.write_session.post.assert_called_once_with(
        f"{TEAM_URL}/addplayer",
        data={"crumb": CRUMB, "apid": 6751, "stat1": "P"},
    )


def test_post_write_raises_already_played(yahoo_client):
    yahoo_client.write_session.post.return_value = _response(
        f"...{ALREADY_PLAYED_MARKER}..."
    )
    with pytest.raises(AlreadyPlayedError):
        yahoo_client._post_write("addplayer", {"apid": 6751})


def test_post_write_raises_max_adds(yahoo_client):
    yahoo_client.write_session.post.return_value = _response(
        f"...{WEEKLY_LIMIT_MARKER}..."
    )
    with pytest.raises(MaxAddsError):
        yahoo_client._post_write("addplayer", {"apid": 6751})


def test_post_write_raises_unintended_waiver(yahoo_client):
    yahoo_client.write_session.post.return_value = _response(
        f"...{WAIVER_CLAIM_PLACED_MARKER}..."
    )
    with pytest.raises(UnintendedWaiverAddError):
        yahoo_client._post_write("addplayer", {"apid": 6751})
