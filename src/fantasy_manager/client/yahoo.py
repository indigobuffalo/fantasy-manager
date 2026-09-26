import datetime
import json
import logging
import re
import urllib.parse
from typing import Callable, Optional, TypeVar

import requests
import yahoo_fantasy_api as yfa
from requests import Response
from yahoo_oauth import OAuth2

from fantasy_manager.client.base import BaseFantasyClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    AlreadyPlayedError,
    FantasyAuthError,
    FantasyUnknownError,
    InvalidRosterPosition,
    MaxAddsError,
    NotOnRosterError,
    OnAnotherTeamError,
    UnintendedWaiverAddError,
)
from fantasy_manager.model.dto.team import RawTeamDto
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.model.enums.player_status import PlayerStatus
from fantasy_manager.model.enums.position import Position, PositionType
from fantasy_manager.model.league import League
from fantasy_manager.model.nhl_team import NhlTeam
from fantasy_manager.model.player import AgnosticPlayer, PlayerName
from fantasy_manager.model.lineup import Lineup
from fantasy_manager.model.team import Team
from fantasy_manager.transform.yahoo import (
    transform_player_by_id_to_api_player,
    transform_yfa_team_data_to_team,
)


logger = logging.getLogger(__name__)


# Markers scanned in the write-transport responses so Yahoo's form-based failures
# map onto the same exceptions the OAuth path already raises. Matched against a
# URL-decoded haystack (redirect URL + body) so they hold regardless of Yahoo's
# encoding — the waiver-claim signal arrives URL-encoded in the redirect's
# `_global_alerts` param, the others as plain text in the body.
ALREADY_PLAYED_MARKER = "player has already played and is no longer"
WEEKLY_LIMIT_MARKER = "You have reached the weekly limit"
WAIVER_CLAIM_PLACED_MARKER = "created a waiver claim for"

# Substrings that identify an OAuth *authorization* failure (Yahoo denying the
# app / a dead token) as opposed to a transient/network error. When any of
# these appear in an error, the read path latches over to the cookie transport.
# Yahoo currently gates Fantasy Sports API reads at the app level, returning
# `oauth_problem="additional_authorization_required"` /
# "This application is not authorized to perform this action.".
_AUTH_ERROR_MARKERS = (
    "not authorized",
    "additional_authorization_required",
    "authorization",
    "token_expired",
    "oauth_problem",
)

# Anchor for the roster player-id blob embedded in the Yahoo team page. The
# pre-refactor tool matched player rows against `var PRCurrTeamPlayers` in the
# page's inline JS; we reuse it to recover rostered player ids over the cookie
# transport.
_ROSTER_JS_ANCHOR = "PRCurrTeamPlayers"

T = TypeVar("T")


class TeamDataNotFoundError(Exception):
    """Error thrown when the team response does not contain expected data"""

    def __init__(self, match_str: str):
        self.message = f"Could not find {match_str} in team response"
        super().__init__(self.message)


class YahooClient(BaseFantasyClient):
    """Class for interacting with Yahoo APIs

    Args:
        BaseClient (_type_): The parent client class.
    """

    def __init__(self, league: League, config: FantasyConfig):
        super().__init__(league=league, config=config)
        self._refresh_context()

    @property
    def team_url(self):
        platform_url = self.config.get_platform_url(
            self.league.platform, PlatformUrl.FANTASY_HOCKEY
        )
        return f"{platform_url}/{self.league.id}/{self.league.team_id}"

    def _refresh_context(self):
        """Sets up the read and write transports and related handles.

        Reads use the official OAuth2 API (``session_context`` + yfa handles).
        Writes use a cookie-backed ``requests.Session``: Yahoo's OAuth app
        tokens are read-only, so writes impersonate a logged-in browser via a
        harvested cookie header plus the ``crumb`` form token replayed on each
        write POST. No write method is routed here yet (see epic #16).
        """
        self.session_context = OAuth2(
            None, None, from_file=self.config.YAHOO_CREDS_FILE
        )
        self.league_handle = yfa.Game(self.session_context, "nhl").to_league(
            self.league.key
        )
        self.team_handle = self.league_handle.to_team(self.league_handle.team_key())

        self.crumb = self.config.YAHOO_CRUMB
        self.write_session = requests.Session()
        self.write_session.headers.update({"cookie": self.config.YAHOO_COOKIE})

        # Decide once, at startup, whether OAuth reads work for this app/token.
        # Yahoo may gate Fantasy Sports API reads at the app level; when it does,
        # reads fall back to the cookie transport (see `_probe_oauth_reads`).
        self._probe_oauth_reads()

    @staticmethod
    def _is_auth_error(err: Exception) -> bool:
        """Classify an exception as an OAuth authorization failure.

        Scans the stringified error for markers that indicate Yahoo denying the
        app or an expired/invalid token (as opposed to a transient network
        blip). Such errors mean OAuth reads won't succeed until auth changes, so
        the read path should latch onto the cookie transport.
        """
        msg = str(err).lower()
        return any(marker in msg for marker in _AUTH_ERROR_MARKERS)

    def _probe_oauth_reads(self) -> None:
        """Run one lightweight OAuth read and cache whether it works.

        Sets ``self._oauth_reads_ok`` so the read dispatch can route directly to
        the working transport without repeatedly retrying a gated OAuth call.

        - success            → OAuth reads work; latch on.
        - auth error         → Yahoo is denying the app; latch to cookie.
        - transient / other  → stay optimistic (leave OAuth on) so a real auth
                               error can still flip the flag mid-session; this
                               avoids permanently falling back on a flaky probe.
        """
        try:
            self.team_handle.roster()
            self._oauth_reads_ok = True
            logger.info("Yahoo reads via OAuth")
        except Exception as err:
            if self._is_auth_error(err):
                self._oauth_reads_ok = False
                logger.info("Yahoo reads via cookie fallback")
            else:
                # Transient/unknown failure: don't permanently latch to cookie.
                self._oauth_reads_ok = True
                logger.warning(
                    "OAuth read probe failed transiently (%s); keeping OAuth "
                    "with a mid-session cookie fallback",
                    err,
                )

    def _dispatch_read(
        self,
        oauth_fn: Callable[[], T],
        cookie_fn: Callable[[], T],
        label: str,
    ) -> T:
        """Route a read to OAuth or cookie based on the latched probe flag.

        When OAuth is enabled, tries it first; a mid-session auth error flips the
        latch to the cookie transport and retries there (subsequent reads then go
        straight to cookie). Non-auth OAuth errors propagate unchanged. If both
        transports fail, raises a ``FantasyAuthError`` naming both.
        """
        if self._oauth_reads_ok:
            try:
                return oauth_fn()
            except Exception as err:
                if not self._is_auth_error(err):
                    raise
                logger.warning(
                    "OAuth read '%s' failed mid-session; flipping to cookie "
                    "fallback",
                    label,
                )
                self._oauth_reads_ok = False
        # Cookie path (either latched off at probe, or just flipped above).
        try:
            return cookie_fn()
        except FantasyAuthError:
            raise
        except Exception as err:
            raise FantasyAuthError(
                f"Both OAuth and cookie read transports failed for '{label}': {err}"
            )

    def _check_locked_players(self) -> None:
        """Ensure all expected players are on roster.

        Raises:
            FantasyAuthError: If not all locked players are on roster.
        """
        rostered_players_ids = [p["player_id"] for p in self.team_handle.roster()]
        locked_player_ids = self.league.locked_players
        if not all(locked in rostered_players_ids for locked in locked_player_ids):
            raise FantasyAuthError("Failed to load team. Check auth.")

    def _check_cookie_auth(self) -> None:
        """Ensure the harvested cookie still authenticates the write transport.

        Mirrors the OAuth ``_check_locked_players`` heuristic against the raw
        team-page HTML: a stale cookie makes Yahoo serve a logged-out page that
        omits our ``locked_players``, so their absence signals a dead cookie.

        Raises:
            FantasyAuthError: If the cookie no longer yields a logged-in team page.
        """
        resp = self.write_session.get(self.team_url)
        if not all(str(pid) in resp.text for pid in self.league.locked_players):
            raise FantasyAuthError(
                "Failed to load team via cookie. Check YAHOO_COOKIE."
            )

    def _post_write(self, path: str, data: dict) -> Response:
        """POST a single write to a Yahoo HTML form endpoint via the cookie transport.

        Injects the stored ``crumb``, POSTs form-encoded to ``{team_url}/{path}``,
        then scans the returned HTML for known failure markers and raises the
        mapped exception. This is a single-shot call: the poll/retry/timeout loop
        stays owned by ``RosterService._execute_with_timeout``.

        Args:
            path (str): Form endpoint under the team URL, e.g. ``"addplayer"``.
            data (dict): Form fields; the ``crumb`` is added automatically.

        Returns:
            Response: The raw POST response, for any further caller inspection.

        Raises:
            AlreadyPlayedError: If the player has already played and is locked.
            MaxAddsError: If the weekly add limit has been reached.
            UnintendedWaiverAddError: If the add unintentionally placed a waiver claim.
        """
        payload = {"crumb": self.crumb, **data}
        resp = self.write_session.post(f"{self.team_url}/{path}", data=payload)
        # Yahoo signals some outcomes only in the redirect URL (a placed waiver
        # claim lands URL-encoded in `_global_alerts`), others in the body HTML.
        # Decode and concatenate both so markers match regardless of encoding.
        haystack = urllib.parse.unquote_plus(resp.url) + resp.text
        if ALREADY_PLAYED_MARKER in haystack:
            raise AlreadyPlayedError(str(data.get("apid")))
        if WEEKLY_LIMIT_MARKER in haystack:
            raise MaxAddsError()
        if WAIVER_CLAIM_PLACED_MARKER in haystack:
            raise UnintendedWaiverAddError()
        return resp

    def refresh(self):
        """Refresh client auth and related handles."""
        self._refresh_context()
        # TODO: moved locked players check to service
        self._check_locked_players()

    def set_lineup(self, lineup: Lineup, lineup_date: datetime.date) -> None:
        """Set lineup for the given date.

        Args:
            lineup (Lineup): lineup of players and their selected positions
            lineup_date (datetime.date): the date to set the lineup
        """
        lineup_date = datetime.date(2024, 12, 12)
        # lineup = Lineup(
        # players=[
        # LineupPlayer(player_id=6751, name="Timo Meier", selected_position=Position.BN.value, ranking=85),
        # LineupPlayer(player_id=8654, name="Dylan Holloway", selected_position=Position.LW.value, ranking=82),
        # LineupPlayer(player_id=8654, name="Mark Stone", selected_position=Position.RW.value, ranking=91),
        # LineupPlayer(player_id=6756, name="Jake Debrusk", selected_position=Position.RW.value, ranking=84),
        # ]
        # )
        as_json = lineup.to_json()
        self.team_handle.change_positions(lineup_date, json.loads(as_json))

    def get_team(self) -> Team:
        """Fetch the team, preferring OAuth and falling back to cookie scraping."""

        def oauth_fn() -> Team:
            yfa_league_team = self.league_handle.teams()[
                self.league_handle.team_key()
            ]
            yfa_team = self.league_handle.to_team(self.league_handle.team_key())
            raw_yfa_dto = RawTeamDto.from_raw_data(yfa_league_team, yfa_team)
            transformed = transform_yfa_team_data_to_team(raw_yfa_dto)
            return Team(**transformed)

        return self._dispatch_read(oauth_fn, self._get_team_via_cookie, "get_team")

    def _get_team_via_cookie(self) -> Team:
        """Best-effort team read over the cookie transport (fallback path).

        This is a markup-dependent scrape: the official OAuth read returns fully
        structured team data, but when Yahoo gates the API we can only recover
        what the browser team page exposes. The rostered player ids are embedded
        in an inline JS blob anchored on ``PRCurrTeamPlayers``; we extract those
        ids and hydrate each player via ``get_player_by_id`` (which itself routes
        through the fallback dispatch). Fields the page doesn't expose (e.g. the
        selected lineup position) are defaulted.

        Raises:
            FantasyAuthError: If the page looks logged-out/stale (our
                ``locked_players`` absent), mirroring ``_check_cookie_auth``.
        """
        resp = self.write_session.get(self.team_url)
        html = resp.text

        # A stale cookie yields a logged-out page that omits our locked players.
        if not all(str(pid) in html for pid in self.league.locked_players):
            raise FantasyAuthError(
                "Failed to load team via cookie. Check YAHOO_COOKIE."
            )

        player_ids = self._scrape_roster_player_ids(html)

        roster: list[dict] = []
        for pid in player_ids:
            # Reuse the player read (best-effort) to hydrate name/positions.
            player = self.get_player_by_id(pid)
            roster.append(
                {
                    "player_id": player.player_id,
                    "name": {"full": player.name.full},
                    "eligible_positions": [
                        pos.value for pos in player.eligible_positions
                    ],
                    "position_type": player.position_type.value,
                    # Selected lineup position isn't reliably scrapable here;
                    # default to bench as a best-effort placeholder.
                    "selected_position": "BN",
                    "status": player.status.value if player.status else "",
                }
            )

        # The browser page doesn't expose the structured team metadata the
        # OAuth path returns, so fill from the known league config best-effort.
        return Team(
            team_id=str(self.league.team_id),
            team_key=self.league.key,
            name=self.league.team_name,
            league_id=self.league.id,
            faab_balance=0,
            roster=roster,
        )

    @staticmethod
    def _scrape_roster_player_ids(html: str) -> list[int]:
        """Extract rostered player ids from the team-page JS blob (best-effort).

        Anchored on the ``PRCurrTeamPlayers`` inline JS var the pre-refactor tool
        keyed off. Yahoo's exact serialization varies, so we pull the ids from
        the segment of markup following that anchor. This is intentionally
        forgiving and markup-dependent; it is the fallback path only.
        """
        anchor_idx = html.find(_ROSTER_JS_ANCHOR)
        segment = html[anchor_idx:] if anchor_idx != -1 else html
        # Grab the assignment blob up to the statement terminator, then the ids.
        blob = segment.split(";", 1)[0]
        ids = re.findall(r"\d+", blob)
        # De-dupe while preserving order.
        seen: set[int] = set()
        ordered: list[int] = []
        for raw in ids:
            pid = int(raw)
            if pid not in seen:
                seen.add(pid)
                ordered.append(pid)
        return ordered

    @staticmethod
    def _handle_client_error(add_id: int, err: Exception):
        add_id_str = str(add_id)
        msg = str(err)
        match msg:
            case str() if "no longer qualifies for that position" in msg:
                raise InvalidRosterPosition(add_id_str, msg)
            case str() if "player has already played" in msg:
                raise AlreadyPlayedError(add_id_str)
            case str() if "player is currently on another team" in msg:
                raise OnAnotherTeamError(add_id_str)
            case str() if "reached the weekly limit" in msg:
                raise MaxAddsError()
            case str() if f"is not on team" in msg:
                raise NotOnRosterError(add_id_str, msg)
            case _:
                raise FantasyUnknownError(
                    f"Error adding player '{add_id_str}':\n\n{msg}"
                )

    def add_player(self, add_id: int) -> None:
        try:
            self.team_handle.add_player(add_id)
            self.league.name_abbr
        except Exception as err:
            self._handle_client_error(add_id=add_id, err=err)

    def add_player_claim(self, add_id, faab=None):
        self.team_handle.claim_player(add_id, faab)

    def drop_player(self, drop_id: int) -> None:
        try:
            self.team_handle.drop_player(drop_id)
        except Exception as err:
            logging.info(f"Error dropping player: {err}")
            raise

    def replace_player(self, add_id: int, drop_id: Optional[int] = None) -> None:
        """
        Replace a player in the team by adding a new player and optionally dropping an existing player.

        Args:
            add_id (int): The ID of the player to be added to the team.
            drop_id (Optional[int]): The ID of the player to be dropped from the team. Defaults to None.

        Returns:
            None

        Raises:
            Exception: If an error occurs during the add and drop operation, it is handled by _handle_client_error.
        """
        try:
            self.team_handle.add_and_drop_players(
                add_player_id=add_id, drop_player_id=drop_id
            )
        except Exception as err:
            self._handle_client_error(add_id=add_id, err=err)

    def replace_player_claim(
        self, add_id: int, drop_id: int, faab: int = None
    ) -> Response:
        return self.team_handle.claim_and_drop_players(add_id, drop_id, faab)

    def cancel_waiver_claim(self, player_id: int) -> None:
        pass

    def get_player_by_id(self, player_id: int) -> AgnosticPlayer:
        """Fetches player from yfa's League.get_player_details endpoint.

        Note: we ignore some data coming back from this endpoint which we may
        want to use in the future.  E.g. advanced stats, points, logo_url, etc.

        Args:
            player_id (int): The id of the player.

        Returns:
            ApiPlayer: an ApiPlayer model instance.
        """
        def oauth_fn() -> AgnosticPlayer:
            yfa_player = self.league_handle.player_details(player_id)[0]
            transformed = transform_player_by_id_to_api_player(yfa_player)
            return AgnosticPlayer(**transformed)

        return self._dispatch_read(
            oauth_fn,
            lambda: self._get_player_by_id_via_cookie(player_id),
            "get_player_by_id",
        )

    def _get_player_by_id_via_cookie(self, player_id: int) -> AgnosticPlayer:
        """Best-effort player read over the cookie transport (fallback path).

        The OAuth endpoint returns rich, structured player data; when Yahoo gates
        the API all we can reliably recover is the player's name by scraping the
        public player page (``sports.yahoo.com/nhl/players/<id>/`` — the pattern
        the pre-refactor tool used). Everything the page doesn't expose is
        defaulted so a valid ``AgnosticPlayer`` can still be constructed:

        - ``position_type``    → SKATER (page doesn't cleanly expose it)
        - ``eligible_positions`` → [UTIL] (a safe, non-empty default)
        - ``status``           → ACTIVE (model default)
        - ``team``             → placeholder NhlTeam (page doesn't expose it here)

        This is intentionally markup-dependent and best-effort.
        """
        resp = self.write_session.get(
            f"https://sports.yahoo.com/nhl/players/{player_id}/"
        )
        # Player page title carries the name, e.g. "<title>Owen Nolan (...)".
        name = resp.text.split("title>")[1].split("(")[0].strip()

        return AgnosticPlayer(
            player_id=player_id,
            name=PlayerName(full=name),
            position_type=PositionType.SKATER,
            eligible_positions=[Position.UTIL],
            status=PlayerStatus.ACTIVE,
            team=NhlTeam(name="", abbr="", team_id=0),
        )
