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
    config.YAHOO_FORCE_COOKIE_READS = False
    config.get_platform_url = Mock(
        return_value="https://hockey.fantasysports.yahoo.com/hockey"
    )
    with patch.object(YahooClient, "_refresh_context"):
        client = YahooClient(league=mock_league, config=config)
    client.crumb = CRUMB
    client.write_session = Mock()
    yield client


def _response(text: str, url: str = "") -> Mock:
    resp = Mock()
    resp.text = text
    resp.url = url
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


def test_post_write_detects_waiver_claim_in_url_encoded_redirect(yahoo_client):
    # Yahoo signals a placed claim only in the redirect URL, URL-encoded (the
    # form observed live: `_global_alerts=...created+a+waiver+claim+for+...`).
    yahoo_client.write_session.post.return_value = _response(
        "clean body, no marker here",
        url=(
            "https://hockey.fantasysports.yahoo.com/hockey/121147/11"
            "?_global_alerts=x%7C%5B%7B%22params%22%3A%5B%22"
            "created+a+waiver+claim+for+Braden+Schneider%22%5D%7D%5D"
        ),
    )
    with pytest.raises(UnintendedWaiverAddError):
        yahoo_client._post_write("addplayer", {"apid": 8659})


# ---------------------------------------------------------------------------
# _is_auth_error classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "This application is not authorized to perform this action.",
        'oauth_problem="additional_authorization_required"',
        "token_expired: please re-auth",
        "Some AUTHORIZATION problem happened",
    ],
)
def test_is_auth_error_true_for_auth_markers(message):
    assert YahooClient._is_auth_error(Exception(message)) is True


def test_is_auth_error_false_for_generic_error():
    assert YahooClient._is_auth_error(Exception("connection reset by peer")) is False


# ---------------------------------------------------------------------------
# _probe_oauth_reads
# ---------------------------------------------------------------------------


def test_probe_sets_flag_true_on_success(yahoo_client):
    yahoo_client.team_handle = Mock()
    yahoo_client.team_handle.roster.return_value = [{"player_id": 1}]

    yahoo_client._probe_oauth_reads()

    assert yahoo_client._oauth_reads_ok is True
    yahoo_client.team_handle.roster.assert_called_once()


def test_probe_latches_cookie_on_auth_error(yahoo_client):
    yahoo_client.team_handle = Mock()
    yahoo_client.team_handle.roster.side_effect = Exception(
        "This application is not authorized to perform this action."
    )

    yahoo_client._probe_oauth_reads()

    assert yahoo_client._oauth_reads_ok is False


def test_probe_stays_optimistic_on_transient_error(yahoo_client):
    yahoo_client.team_handle = Mock()
    yahoo_client.team_handle.roster.side_effect = Exception("connection timed out")

    yahoo_client._probe_oauth_reads()

    # Transient failure must NOT permanently latch to cookie.
    assert yahoo_client._oauth_reads_ok is True


def test_probe_forced_cookie_skips_oauth_read(yahoo_client):
    yahoo_client.config.YAHOO_FORCE_COOKIE_READS = True
    yahoo_client.team_handle = Mock()

    status = yahoo_client._probe_oauth_reads()

    # Forced cookie mode latches to cookie without touching OAuth at all.
    assert status == "forced"
    assert yahoo_client._oauth_reads_ok is False
    yahoo_client.team_handle.roster.assert_not_called()


# ---------------------------------------------------------------------------
# _verify_read_auth (startup auth self-check)
# ---------------------------------------------------------------------------


def test_verify_read_auth_passes_when_both_transports_work(yahoo_client):
    yahoo_client._probe_oauth_reads = Mock(return_value="ok")
    yahoo_client._check_cookie_reads = Mock(return_value=True)

    # Should not raise when at least one transport works.
    yahoo_client._verify_read_auth()


def test_verify_read_auth_passes_when_only_oauth_works(yahoo_client):
    yahoo_client._probe_oauth_reads = Mock(return_value="ok")
    yahoo_client._check_cookie_reads = Mock(return_value=False)

    yahoo_client._verify_read_auth()


def test_verify_read_auth_passes_when_only_cookie_works(yahoo_client):
    yahoo_client._probe_oauth_reads = Mock(return_value="auth_error")
    yahoo_client._check_cookie_reads = Mock(return_value=True)

    yahoo_client._verify_read_auth()


def test_verify_read_auth_passes_when_forced_cookie_works(yahoo_client):
    yahoo_client._probe_oauth_reads = Mock(return_value="forced")
    yahoo_client._check_cookie_reads = Mock(return_value=True)

    yahoo_client._verify_read_auth()


def test_verify_read_auth_hard_fails_when_neither_transport_works(yahoo_client):
    yahoo_client._probe_oauth_reads = Mock(return_value="auth_error")
    yahoo_client._check_cookie_reads = Mock(return_value=False)

    with pytest.raises(FantasyAuthError):
        yahoo_client._verify_read_auth()


def test_verify_read_auth_hard_fails_when_forced_but_cookie_dead(yahoo_client):
    yahoo_client._probe_oauth_reads = Mock(return_value="forced")
    yahoo_client._check_cookie_reads = Mock(return_value=False)

    with pytest.raises(FantasyAuthError):
        yahoo_client._verify_read_auth()


def test_check_cookie_reads_returns_false_on_stale_cookie(yahoo_client):
    yahoo_client.write_session.get.return_value = _response("logged out; only 1 and 2")
    assert yahoo_client._check_cookie_reads() is False


def test_check_cookie_reads_returns_true_when_authed(yahoo_client):
    yahoo_client.write_session.get.return_value = _response("roster has 1, 2 and 3")
    assert yahoo_client._check_cookie_reads() is True


# ---------------------------------------------------------------------------
# refresh (write-path auth check honors the active read transport)
# ---------------------------------------------------------------------------


def test_refresh_checks_oauth_when_reads_ok(yahoo_client):
    yahoo_client._refresh_context = Mock()
    yahoo_client._oauth_reads_ok = True
    yahoo_client._check_locked_players = Mock()
    yahoo_client._check_cookie_auth = Mock()

    yahoo_client.refresh()

    yahoo_client._check_locked_players.assert_called_once()
    yahoo_client._check_cookie_auth.assert_not_called()


def test_refresh_checks_cookie_when_oauth_gated(yahoo_client):
    # The gated scenario: OAuth reads are off, so refresh must NOT touch the
    # OAuth locked-players check (it would raise) and must verify the cookie.
    yahoo_client._refresh_context = Mock()
    yahoo_client._oauth_reads_ok = False
    yahoo_client._check_locked_players = Mock()
    yahoo_client._check_cookie_auth = Mock()

    yahoo_client.refresh()

    yahoo_client._check_cookie_auth.assert_called_once()
    yahoo_client._check_locked_players.assert_not_called()


# ---------------------------------------------------------------------------
# _dispatch_read
# ---------------------------------------------------------------------------


def test_dispatch_uses_oauth_when_flag_true(yahoo_client):
    yahoo_client._oauth_reads_ok = True
    oauth_fn = Mock(return_value="oauth-result")
    cookie_fn = Mock(return_value="cookie-result")

    result = yahoo_client._dispatch_read(oauth_fn, cookie_fn, "label")

    assert result == "oauth-result"
    oauth_fn.assert_called_once()
    cookie_fn.assert_not_called()


def test_dispatch_uses_cookie_when_flag_false_no_oauth_attempt(yahoo_client):
    yahoo_client._oauth_reads_ok = False
    oauth_fn = Mock(return_value="oauth-result")
    cookie_fn = Mock(return_value="cookie-result")

    result = yahoo_client._dispatch_read(oauth_fn, cookie_fn, "label")

    assert result == "cookie-result"
    oauth_fn.assert_not_called()
    cookie_fn.assert_called_once()


def test_dispatch_flips_to_cookie_on_midsession_auth_error(yahoo_client):
    yahoo_client._oauth_reads_ok = True
    oauth_fn = Mock(
        side_effect=Exception("additional_authorization_required")
    )
    cookie_fn = Mock(return_value="cookie-result")

    result = yahoo_client._dispatch_read(oauth_fn, cookie_fn, "label")

    assert result == "cookie-result"
    assert yahoo_client._oauth_reads_ok is False
    oauth_fn.assert_called_once()
    cookie_fn.assert_called_once()

    # Subsequent reads stay on cookie (no further OAuth attempts).
    oauth_fn.reset_mock()
    cookie_fn.reset_mock()
    yahoo_client._dispatch_read(oauth_fn, cookie_fn, "label")
    oauth_fn.assert_not_called()
    cookie_fn.assert_called_once()


def test_dispatch_propagates_non_auth_oauth_error(yahoo_client):
    yahoo_client._oauth_reads_ok = True
    oauth_fn = Mock(side_effect=ValueError("some parsing bug"))
    cookie_fn = Mock(return_value="cookie-result")

    with pytest.raises(ValueError):
        yahoo_client._dispatch_read(oauth_fn, cookie_fn, "label")

    # Flag unchanged; cookie never consulted for a non-auth failure.
    assert yahoo_client._oauth_reads_ok is True
    cookie_fn.assert_not_called()


def test_dispatch_raises_fantasy_auth_error_when_both_fail(yahoo_client):
    yahoo_client._oauth_reads_ok = True
    oauth_fn = Mock(side_effect=Exception("not authorized"))
    cookie_fn = Mock(side_effect=Exception("cookie also broke"))

    with pytest.raises(FantasyAuthError) as exc_info:
        yahoo_client._dispatch_read(oauth_fn, cookie_fn, "get_team")

    msg = str(exc_info.value)
    assert "OAuth" in msg and "cookie" in msg and "get_team" in msg


def test_dispatch_preserves_cookie_fantasy_auth_error(yahoo_client):
    yahoo_client._oauth_reads_ok = False
    cookie_fn = Mock(side_effect=FantasyAuthError("stale cookie"))

    with pytest.raises(FantasyAuthError) as exc_info:
        yahoo_client._dispatch_read(Mock(), cookie_fn, "get_team")

    assert "stale cookie" in str(exc_info.value)


# ---------------------------------------------------------------------------
# get_team / get_player_by_id routing
# ---------------------------------------------------------------------------


def test_get_team_routes_via_oauth_when_reads_ok(yahoo_client):
    yahoo_client._oauth_reads_ok = True
    sentinel = object()
    yahoo_client.league_handle = Mock()
    yahoo_client.league_handle.team_key.return_value = "tk"
    yahoo_client.league_handle.teams.return_value = {"tk": {}}
    yahoo_client._get_team_via_cookie = Mock()
    with patch(
        "fantasy_manager.client.yahoo.transform_yfa_team_data_to_team",
        return_value={},
    ), patch(
        "fantasy_manager.client.yahoo.RawTeamDto"
    ), patch(
        "fantasy_manager.client.yahoo.Team", return_value=sentinel
    ):
        result = yahoo_client.get_team()

    assert result is sentinel
    yahoo_client._get_team_via_cookie.assert_not_called()


def test_get_team_routes_via_cookie_when_reads_not_ok(yahoo_client):
    yahoo_client._oauth_reads_ok = False
    sentinel = object()
    yahoo_client.league_handle = Mock()
    yahoo_client._get_team_via_cookie = Mock(return_value=sentinel)

    result = yahoo_client.get_team()

    assert result is sentinel
    yahoo_client.league_handle.teams.assert_not_called()


def test_get_player_by_id_routes_via_cookie_when_reads_not_ok(yahoo_client):
    yahoo_client._oauth_reads_ok = False
    sentinel = object()
    yahoo_client.league_handle = Mock()
    yahoo_client._get_player_by_id_via_cookie = Mock(return_value=sentinel)

    result = yahoo_client.get_player_by_id(6751)

    assert result is sentinel
    yahoo_client._get_player_by_id_via_cookie.assert_called_once_with(6751)
    yahoo_client.league_handle.player_details.assert_not_called()


# ---------------------------------------------------------------------------
# cookie readers
# ---------------------------------------------------------------------------


def test_get_team_via_cookie_raises_on_stale_session(yahoo_client):
    yahoo_client.write_session.get.return_value = _response("logged out; only 1 and 2")
    with pytest.raises(FantasyAuthError):
        yahoo_client._get_team_via_cookie()


def test_get_player_by_id_via_cookie_scrapes_name(yahoo_client):
    yahoo_client.write_session.get.return_value = _response(
        "<title>Owen Nolan (RW) - San Jose Sharks</title>"
    )

    player = yahoo_client._get_player_by_id_via_cookie(1)

    assert player.player_id == 1
    assert player.name.full == "Owen Nolan"


def test_scrape_roster_player_ids_reads_only_the_array():
    # Yahoo serializes the roster as a JSON array; adjacent vars (e.g. the
    # opponent team id) must NOT bleed into the parse.
    html = (
        'x"varPRCurrTeamPlayers" : [6877, 7905, 6368, 30546],\n'
        '"varPROppTeamID" : 99121147,\n'
    )
    assert YahooClient._scrape_roster_player_ids(html) == [6877, 7905, 6368, 30546]


def test_scrape_roster_player_ids_returns_empty_without_anchor():
    assert YahooClient._scrape_roster_player_ids("<html>no roster here</html>") == []


def test_scrape_selected_positions_reads_selected_option():
    # Selected slot per player, upper-cased to match Position values
    # (Util -> UTIL, IR+ stays IR+); unselected options are ignored.
    html = (
        '<select name="6877"><option value="LW">LW</option>'
        '<option value="Util">Util</option>'
        '<option value="BN" selected>BN</option></select>'
        '<select name="6817"><option value="G">G</option>'
        '<option value="IR+" selected>IR+</option></select>'
    )
    assert YahooClient._scrape_selected_positions(html) == {6877: "BN", 6817: "IR+"}


def test_scrape_selected_positions_empty_without_selects():
    assert YahooClient._scrape_selected_positions("<html>nothing</html>") == {}


def test_scrape_eligible_positions_excludes_bench_and_ir_slots():
    # Eligible positions are the select's options minus lineup-only slots
    # (BN/IR/IR+/IR-); values are upper-cased (Util -> UTIL).
    html = (
        '<select name="6877"><option value="LW">LW</option>'
        '<option value="Util">Util</option>'
        '<option value="BN" selected>BN</option></select>'
        '<select name="6817"><option value="G">G</option>'
        '<option value="BN">BN</option>'
        '<option value="IR+" selected>IR+</option></select>'
    )
    assert YahooClient._scrape_eligible_positions(html) == {
        6877: ["LW", "UTIL"],
        6817: ["G"],
    }


def test_refresh_context_forced_cookie_skips_oauth_construction(mock_league):
    # With reads forced to cookie, _refresh_context must not construct the OAuth
    # transport at all (constructing OAuth2 with no creds prompts interactively).
    config = Mock(spec=FantasyConfig)
    config.YAHOO_COOKIE = "cookie-header"
    config.YAHOO_CRUMB = CRUMB
    config.YAHOO_CREDS_FILE = None
    config.YAHOO_FORCE_COOKIE_READS = True
    config.get_platform_url = Mock(
        return_value="https://hockey.fantasysports.yahoo.com/hockey"
    )
    with patch("fantasy_manager.client.yahoo.OAuth2") as mock_oauth, patch(
        "fantasy_manager.client.yahoo.yfa"
    ) as mock_yfa, patch.object(YahooClient, "_verify_read_auth"):
        client = YahooClient(league=mock_league, config=config)

    mock_oauth.assert_not_called()
    mock_yfa.Game.assert_not_called()
    assert client.session_context is None
    assert client.league_handle is None
    assert client.team_handle is None
