import datetime
import json
import logging
import re
import urllib.parse
from enum import Enum
from html import unescape
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
    MaxAddsError,
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

# On the team page each rostered player has a position-picker
# `<select name="<player_id>">` whose currently-selected `<option>` is the
# player's assigned slot (C/LW/RW/D/G/Util/BN/IR/IR+). We scrape that selection
# to recover real lineup positions over the cookie transport.
_POSITION_SELECT_RE = re.compile(r'<select name="(\d+)".*?</select>', re.DOTALL)
_SELECTED_OPTION_RE = re.compile(r'<option value="([^"]+)"\s+selected')
_OPTION_VALUE_RE = re.compile(r'<option value="([^"]+)"')

# Each rostered player links to its public player page; the link text is the
# player's name, e.g. `<a href="/nhl/players/6877/…">Kirill Kaprizov</a>`. The
# `[^>]*>` consumes the rest of the opening tag so an image-only link (no text
# before the next `<`) simply doesn't match. Markup-dependent, fallback-only.
_PLAYER_NAME_RE = re.compile(r"/nhl/players/(\d+)[^>]*>([^<]{2,40})</a>")

# Lineup slots offered by the position `<select>` that aren't position
# eligibilities — filtered out when recovering a player's eligible positions.
_NON_ELIGIBLE_SLOTS = frozenset({"BN", "IR", "IR+", "IR-"})

T = TypeVar("T")


class ReadProbeStatus(Enum):
    """Outcome of the startup OAuth read probe (``_probe_oauth_reads``).

    Distinguishes the reasons the read path did (or didn't) latch onto OAuth, so
    callers branch on a named member instead of a bare string:

    - ``FORCED``     → probe skipped; latched to cookie (``YAHOO_FORCE_COOKIE_READS``).
    - ``OK``         → OAuth reads work; latch on.
    - ``AUTH_ERROR`` → Yahoo is denying the app; latch to cookie.
    - ``TRANSIENT``  → probe failed on a non-auth error, so stay optimistic and
                       leave OAuth on (a real auth error can still flip it later).
    """

    FORCED = "forced"
    OK = "ok"
    AUTH_ERROR = "auth_error"
    TRANSIENT = "transient"


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

        Reads prefer the official OAuth2 API (``session_context`` + yfa handles),
        falling back to the cookie transport. Writes use a cookie-backed
        ``requests.Session``: Yahoo's OAuth app tokens are read-only, so writes
        impersonate a logged-in browser via a harvested cookie header plus the
        ``crumb`` form token replayed on each write POST.
        """
        # Cookie/crumb transport: powers writes and the read fallback.
        self.crumb = self.config.YAHOO_CRUMB
        self.write_session = requests.Session()
        self.write_session.headers.update({"cookie": self.config.YAHOO_COOKIE})

        # OAuth read transport. Constructing OAuth2 performs the token handshake
        # and, with no creds file, drops into an interactive verifier prompt — so
        # when reads are forced onto the cookie transport there's no OAuth path to
        # build, and we skip it entirely. The read dispatch never touches these
        # handles while `_oauth_reads_ok` is False.
        if self.config.YAHOO_FORCE_COOKIE_READS:
            self.session_context = None
            self.league_handle = None
            self.team_handle = None
        else:
            self.session_context = OAuth2(
                None, None, from_file=self.config.YAHOO_CREDS_FILE
            )
            self.league_handle = yfa.Game(self.session_context, "nhl").to_league(
                self.league.key
            )
            self.team_handle = self.league_handle.to_team(
                self.league_handle.team_key()
            )

        # At startup, confirm the read auth situation for both transports: pick
        # the read transport (OAuth vs cookie) and hard-fail if neither works, so
        # a broken setup surfaces immediately rather than on the first read.
        self._verify_read_auth()

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

    def _probe_oauth_reads(self) -> ReadProbeStatus:
        """Run one lightweight OAuth read and cache whether it works.

        Sets ``self._oauth_reads_ok`` so the read dispatch can route directly to
        the working transport without repeatedly retrying a gated OAuth call, and
        returns a ``ReadProbeStatus`` describing the outcome for the startup auth
        check.
        """
        # An operator who knows OAuth reads are gated can skip the probe (and its
        # guaranteed-failing OAuth call) by setting YAHOO_FORCE_COOKIE_READS.
        if self.config.YAHOO_FORCE_COOKIE_READS:
            self._oauth_reads_ok = False
            logger.info(
                "Yahoo reads via cookie fallback (forced by YAHOO_FORCE_COOKIE_READS)"
            )
            return ReadProbeStatus.FORCED
        try:
            self.team_handle.roster()
            self._oauth_reads_ok = True
            logger.info("Yahoo reads via OAuth")
            return ReadProbeStatus.OK
        except Exception as err:
            if self._is_auth_error(err):
                self._oauth_reads_ok = False
                logger.info("Yahoo reads via cookie fallback")
                return ReadProbeStatus.AUTH_ERROR
            # Transient/unknown failure: don't permanently latch to cookie.
            self._oauth_reads_ok = True
            logger.warning(
                "OAuth read probe failed transiently (%s); keeping OAuth "
                "with a mid-session cookie fallback",
                err,
            )
            return ReadProbeStatus.TRANSIENT

    def _check_cookie_reads(self) -> bool:
        """Return whether the cookie transport can currently read the team page.

        Wraps ``_check_locked_players_via_cookie`` (which raises on a stale/logged-out cookie)
        into a boolean so the startup auth check can report on both transports
        without short-circuiting on the first failure.
        """
        try:
            self._check_locked_players_via_cookie()
            return True
        except Exception as err:
            logger.debug("Cookie read check failed: %s", err)
            return False

    def _verify_read_auth(self) -> None:
        """Confirm the read-auth situation for both transports at startup.

        Runs the OAuth probe (unless forced to cookie) and a cookie read check,
        logs the combined state so the auth picture is obvious up front, and
        hard-fails when *neither* transport can read.

        - both work        → INFO, reads use OAuth (writes' cookie also healthy).
        - only OAuth works  → WARNING, cookie transport is down (writes will fail).
        - only cookie works → INFO/WARNING, reads use the cookie fallback.
        - neither works     → raise ``FantasyAuthError`` (fail fast).
        """
        probe_status = self._probe_oauth_reads()
        oauth_reads_ok = probe_status == ReadProbeStatus.OK
        cookie_reads_ok = self._check_cookie_reads()

        if oauth_reads_ok and cookie_reads_ok:
            logger.info(
                "Yahoo auth OK: OAuth and cookie read transports both working"
            )
        elif oauth_reads_ok:
            logger.warning(
                "Yahoo auth: OAuth reads working, but cookie transport is NOT — "
                "writes (add/drop/waivers/lineup) will fail. Check YAHOO_COOKIE."
            )
        elif cookie_reads_ok:
            if probe_status == ReadProbeStatus.FORCED:
                logger.info(
                    "Yahoo auth OK: cookie read transport working "
                    "(OAuth probe skipped via YAHOO_FORCE_COOKIE_READS)"
                )
            else:
                logger.warning(
                    "Yahoo auth: OAuth reads NOT working; using cookie read "
                    "fallback. Reads and writes both depend on YAHOO_COOKIE."
                )
        else:
            raise FantasyAuthError(
                "Yahoo auth failed: neither the OAuth nor the cookie read "
                "transport is working. Check YAHOO_CREDS_FILE (OAuth) and "
                "YAHOO_COOKIE/YAHOO_CRUMB (cookie)."
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
        transports fail, raises a ``FantasyAuthError`` naming the transports that
        were actually tried.
        """
        oauth_attempted = False
        if self._oauth_reads_ok:
            oauth_attempted = True
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
            # Name only the transports we actually exercised: when OAuth was
            # latched off, it was never tried, so "both failed" would mislead.
            tried = "OAuth and cookie" if oauth_attempted else "cookie"
            raise FantasyAuthError(
                f"The {tried} read transport(s) failed for '{label}': {err}"
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

    def _check_locked_players_via_cookie(self) -> None:
        """Ensure the harvested cookie still authenticates the cookie transport.

        Backs both the cookie *read* fallback and the cookie *write* path, which
        share the same ``YAHOO_COOKIE`` session. Mirrors the OAuth
        ``_check_locked_players`` heuristic against the raw team-page HTML: a
        stale cookie makes Yahoo serve a logged-out page that omits our
        ``locked_players``, so their absence signals a dead cookie.

        Raises:
            FantasyAuthError: If the cookie no longer yields a logged-in team page.
        """
        resp = self.write_session.get(self.team_url)
        if not all(str(pid) in resp.text for pid in self.league.locked_players):
            raise FantasyAuthError(
                "Failed to load team via cookie. Check YAHOO_COOKIE."
            )

    def _post_write(
        self, path: str, data: dict, allow_waiver_claim: bool = False
    ) -> Response:
        """POST a single write to a Yahoo HTML form endpoint via the cookie transport.

        Injects the stored ``crumb``, POSTs form-encoded to ``{team_url}/{path}``,
        then scans the returned HTML for known failure markers and raises the
        mapped exception. This is a single-shot call: the poll/retry/timeout loop
        stays owned by ``RosterService._execute_with_timeout``.

        Args:
            path (str): Form endpoint under the team URL, e.g. ``"addplayer"``.
            data (dict): Form fields; the ``crumb`` is added automatically.
            allow_waiver_claim (bool): When ``True``, the
                ``WAIVER_CLAIM_PLACED_MARKER`` ("created a waiver claim for") is
                treated as success rather than raising ``UnintendedWaiverAddError``.
                A deliberate waiver claim (``add_player_claim`` /
                ``replace_player_claim``) rides the same ``addplayer`` form as a
                plain add, so that marker is the *expected* outcome and must not
                be mapped to the "unintended" error. ``AlreadyPlayedError`` and
                ``MaxAddsError`` are still raised regardless. Defaults to False.

        Returns:
            Response: The raw POST response, for any further caller inspection.

        Raises:
            AlreadyPlayedError: If the player has already played and is locked.
            MaxAddsError: If the weekly add limit has been reached.
            UnintendedWaiverAddError: If the add unintentionally placed a waiver
                claim (suppressed when ``allow_waiver_claim`` is True).
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
        if WAIVER_CLAIM_PLACED_MARKER in haystack and not allow_waiver_claim:
            raise UnintendedWaiverAddError()
        return resp

    def refresh(self):
        """Refresh client auth and related handles.

        ``_refresh_context`` already runs the startup read-auth self-check
        (``_verify_read_auth``), which hard-fails if neither transport can read.
        We then re-assert that *our* team actually loads, over whichever read
        transport is active: OAuth when the probe latched it on, otherwise the
        cookie transport. Checking OAuth unconditionally would raise in the
        gated scenario (Yahoo denying app reads) even when the cookie path is
        healthy — which would block every write, the exact thing this transport
        split exists to keep working.
        """
        self._refresh_context()
        # TODO: move the locked-players check into the service layer.
        if self._oauth_reads_ok:
            self._check_locked_players()
        else:
            self._check_locked_players_via_cookie()

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
        what the browser team page exposes — and everything we need is on that
        single page, so this issues exactly one request:

        - rostered player ids from the ``PRCurrTeamPlayers`` inline JS blob;
        - each player's name from its ``/nhl/players/<id>/…>NAME</a>`` link;
        - the assigned lineup slot (incl. IR/IR+) and eligible positions from the
          per-player position ``<select>``.

        Fields the page doesn't expose (``position_type``, ``status``) are
        defaulted, matching the structured model's own defaults.

        Raises:
            FantasyAuthError: If the page looks logged-out/stale (our
                ``locked_players`` absent), mirroring ``_check_locked_players_via_cookie``.
        """
        resp = self.write_session.get(self.team_url)
        html = resp.text

        # A stale cookie yields a logged-out page that omits our locked players.
        if not all(str(pid) in html for pid in self.league.locked_players):
            raise FantasyAuthError(
                "Failed to load team via cookie. Check YAHOO_COOKIE."
            )

        player_ids = self._scrape_roster_player_ids(html)
        names = self._scrape_player_names(html)
        selected_positions = self._scrape_selected_positions(html)
        eligible_positions = self._scrape_eligible_positions(html)

        roster: list[dict] = []
        for pid in player_ids:
            # Everything is scraped from the one team page; fields it doesn't
            # expose fall back to the model's own defaults.
            roster.append(
                {
                    "player_id": pid,
                    "name": {"full": names.get(pid, str(pid))},
                    # Eligibilities scraped from the position <select>; a locked/
                    # played player has static text (no select), so default to a
                    # safe non-empty eligibility.
                    "eligible_positions": eligible_positions.get(
                        pid, [Position.UTIL.value]
                    ),
                    # Not exposed on the page; default to skater.
                    "position_type": PositionType.SKATER.value,
                    # Assigned slot scraped from the select; default to bench
                    # when the player's select isn't present.
                    "selected_position": selected_positions.get(pid, "BN"),
                    # Not exposed on the page; default to active.
                    "status": PlayerStatus.ACTIVE.value,
                }
            )

        # The browser page doesn't expose the structured team metadata the
        # OAuth path returns, so fill from the known league config best-effort.
        return Team(
            team_id=str(self.league.team_id),
            team_key=self.league.key,
            name=self.league.team_name,
            league_id=self.league.id,
            # Team.convert_to_int only coerces str input, so pass "0" not 0.
            faab_balance="0",
            roster=roster,
        )

    @staticmethod
    def _scrape_roster_player_ids(html: str) -> list[int]:
        """Extract rostered player ids from the team-page JS blob (best-effort).

        Anchored on the ``PRCurrTeamPlayers`` inline JS var the pre-refactor tool
        keyed off. Yahoo serializes it as a JSON array of player ids, e.g.::

            "varPRCurrTeamPlayers" : [6877, 7905, 6368, ...],

        so we take only the ids between the ``[`` and ``]`` that follow the
        anchor — bounding the parse to this one array (grabbing the wider markup
        would also pull in adjacent vars like ``varPROppTeamID``). Markup-
        dependent and fallback-only.
        """
        anchor_idx = html.find(_ROSTER_JS_ANCHOR)
        if anchor_idx == -1:
            return []
        open_idx = html.find("[", anchor_idx)
        close_idx = html.find("]", open_idx)
        if open_idx == -1 or close_idx == -1:
            return []
        blob = html[open_idx + 1 : close_idx]
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
    def _scrape_player_names(html: str) -> dict[int, str]:
        """Map each player id to its name from the team-page links (best-effort).

        Every rostered player links to its public player page with the name as
        the link text (see ``_PLAYER_NAME_RE``). This recovers all names from the
        single team page, so the cookie team read needs no per-player requests.
        HTML entities in names (e.g. accents) are unescaped. First link wins if a
        player id somehow appears more than once. Markup-dependent, fallback-only.
        """
        names: dict[int, str] = {}
        for pid_str, raw_name in _PLAYER_NAME_RE.findall(html):
            pid = int(pid_str)
            if pid not in names:
                names[pid] = unescape(raw_name).strip()
        return names

    @staticmethod
    def _scrape_selected_positions(html: str) -> dict[int, str]:
        """Map each rostered player id to its selected lineup slot (best-effort).

        Each player's position picker on the team page is a
        ``<select name="<player_id>">`` whose ``selected`` ``<option>`` is the
        assigned slot, e.g.::

            <select name="6817"><option value="G">G</option>
              <option value="IR+" selected>IR+</option></select>

        Values are upper-cased so they line up with ``Position`` enum values
        (``Util`` → ``UTIL``, ``IR+`` stays ``IR+``). Markup-dependent and
        fallback-only.
        """
        positions: dict[int, str] = {}
        for match in _POSITION_SELECT_RE.finditer(html):
            selected = _SELECTED_OPTION_RE.search(match.group(0))
            if selected:
                positions[int(match.group(1))] = selected.group(1).upper()
        return positions

    @staticmethod
    def _scrape_eligible_positions(html: str) -> dict[int, list[str]]:
        """Map each player id to its eligible positions (best-effort).

        The same position ``<select>`` lists every slot a player can fill; the
        real position eligibilities are those options minus the bench/IR lineup
        slots (``BN``/``IR``/``IR+``/``IR-``). Values are upper-cased to match
        ``Position`` (e.g. ``Util`` → ``UTIL``). Markup-dependent, fallback-only.

        Note a deliberate divergence from the OAuth path: the OAuth transform
        passes Yahoo's ``eligible_positions`` through verbatim (which can include
        bench/IR slots), whereas this scrape strips them so eligibilities mean
        only real positions. ``UTIL`` is kept by both paths.
        """
        eligible: dict[int, list[str]] = {}
        for match in _POSITION_SELECT_RE.finditer(html):
            values: list[str] = []
            for value in _OPTION_VALUE_RE.findall(match.group(0)):
                upper = value.upper()
                if upper not in _NON_ELIGIBLE_SLOTS and upper not in values:
                    values.append(upper)
            if values:
                eligible[int(match.group(1))] = values
        return eligible

    # add/drop/replace and the waiver-claim methods (add_player_claim /
    # replace_player_claim / cancel_waiver_claim) ride the cookie transport
    # because Yahoo has OAuth writes gated. The prior OAuth implementations (yfa
    # team_handle.add_player / drop_player / add_and_drop_players and
    # claim_player / claim_and_drop_players, plus the _handle_client_error string
    # mapper) live in commit b510c64 if Yahoo ever reopens OAuth write access.
    def add_player(self, add_id: int) -> None:
        """Add a free agent to the roster over the cookie write transport.

        POSTs Yahoo's ``addplayer`` form (``stage=3, stat1=P, stat2=P``). This is
        a single-shot call; ``RosterService._execute_with_timeout`` owns the
        poll/retry/timeout loop and the post-add roster verification.

        Args:
            add_id (int): The id of the player to add.

        Raises:
            AlreadyPlayedError, MaxAddsError, UnintendedWaiverAddError: As mapped
                from the response markers by ``_post_write``.
        """
        self._post_write(
            "addplayer",
            {"stage": "3", "stat1": "P", "stat2": "P", "apid": add_id},
        )

    def add_player_claim(self, add_id: int, faab: int = None) -> Response:
        """Place a waiver claim to add a free agent, over the cookie write transport.

        Rides the same ``addplayer`` form as :meth:`add_player`; when the target
        player is on waivers Yahoo records a waiver claim rather than an instant
        add. The "created a waiver claim for" marker — which ``_post_write``
        treats as an *unintended* claim for plain adds — is the *expected
        success* signal here, so we pass ``allow_waiver_claim=True`` to suppress
        that mapping. Single-shot; ``RosterService`` owns any retry/timeout loop.

        Args:
            add_id (int): The id of the player to claim.
            faab (int, optional): FAAB bid amount, submitted as the ``faab`` form
                field (verified against a live waiver-claim request). Omitted from
                the POST body when None. Defaults to None.

        Returns:
            Response: The raw waiver-claim POST response.
        """
        data = {"stage": "3", "stat1": "P", "stat2": "P", "apid": add_id}
        if faab is not None:
            data["faab"] = faab
        return self._post_write("addplayer", data, allow_waiver_claim=True)

    def drop_player(self, drop_id: int, drop_name: Optional[str] = None) -> None:
        """Drop a rostered player over the cookie write transport.

        POSTs Yahoo's ``dropplayer`` form. The commit stage differs from the add
        form (``stage=2, stat1=S, stat2=D``, observed live on the drop
        confirmation page), and the submit button must be present for Yahoo to
        commit the drop rather than re-render the confirmation page.

        Yahoo renders the submit button's value as the full label ``"Drop
        <Player Name>"`` (verified against the live confirmation form), so when a
        name is supplied we reproduce it exactly; otherwise we fall back to a
        bare ``"Drop"``.

        Args:
            drop_id (int): The id of the player to drop.
            drop_name (Optional[str]): The player's full name, used to match the
                live submit-button value. Defaults to None.
        """
        submit_value = f"Drop {drop_name}" if drop_name else "Drop"
        self._post_write(
            "dropplayer",
            {
                "stage": "2",
                "stat1": "S",
                "stat2": "D",
                "dpid": drop_id,
                "submit_drop_player": submit_value,
            },
        )

    def replace_player(self, add_id: int, drop_id: Optional[int] = None) -> None:
        """Add a player and, optionally, drop one in the same transaction.

        Rides the same ``addplayer`` form as :meth:`add_player`; supplying
        ``dpid`` makes Yahoo drop that player as part of the add. Single-shot:
        the retry/timeout loop stays in ``RosterService``.

        Args:
            add_id (int): The id of the player to add.
            drop_id (Optional[int]): The id of the player to drop. Defaults to None.

        Raises:
            AlreadyPlayedError, MaxAddsError, UnintendedWaiverAddError: As mapped
                from the response markers by ``_post_write``.
        """
        data = {"stage": "3", "stat1": "P", "stat2": "P", "apid": add_id}
        if drop_id is not None:
            data["dpid"] = drop_id
        self._post_write("addplayer", data)

    def replace_player_claim(
        self, add_id: int, drop_id: int, faab: int = None
    ) -> Response:
        """Place a waiver claim to add one player and drop another, over the cookie transport.

        Same ``addplayer`` form as :meth:`add_player_claim` plus ``dpid`` for the
        drop, mirroring how :meth:`replace_player` extends :meth:`add_player`. The
        waiver-claim success marker is expected, so ``allow_waiver_claim=True``.

        Args:
            add_id (int): The id of the player to claim.
            drop_id (int): The id of the player to drop.
            faab (int, optional): FAAB bid amount, submitted as the ``faab`` form
                field (verified against a live waiver-claim request). Omitted from
                the POST body when None. Defaults to None.

        Returns:
            Response: The raw waiver-claim POST response.
        """
        data = {
            "stage": "3",
            "stat1": "P",
            "stat2": "P",
            "apid": add_id,
            "dpid": drop_id,
        }
        if faab is not None:
            data["faab"] = faab
        return self._post_write("addplayer", data, allow_waiver_claim=True)

    def cancel_waiver_claim(
        self, add_id: int, drop_id: Optional[int] = None
    ) -> Response:
        """Cancel a pending waiver claim over the cookie write transport.

        POSTs Yahoo's ``editwaiver`` form. The claim is identified by a
        ``claim_id`` of the form ``<team_id>_<add_id>_<drop_id>`` (``drop_id`` is
        ``0`` for an add-only claim), where ``team_id`` is this team's number in
        the league — the same value that trails the team URL
        (``/<league_id>/<team_id>``). Verified against a live cancel request
        (``claim_id=11_<apid>_<dpid>`` for team 11); the pre-refactor template in
        commit ``c312208`` was the degenerate team-1 add-only case
        (``1_<pid>_0``). The form echoes ``apid``/``dpid`` with a ``faab`` of 0,
        and the ``crumb`` is injected by ``_post_write``. Single-shot.

        Args:
            add_id (int): The id of the claimed (to-be-added) player.
            drop_id (Optional[int]): The id of the player the claim would drop,
                if any. Defaults to None (add-only claim).

        Returns:
            Response: The raw cancel POST response.
        """
        dpid = drop_id if drop_id is not None else 0
        return self._post_write(
            "editwaiver",
            {
                "stage": "2",
                "claim_id": f"{self.league.team_id}_{add_id}_{dpid}",
                "mode": "edit",
                "apid": add_id,
                "dpid": dpid,
                "faab": 0,
                "s": "Cancel Waiver",
            },
        )

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

        Raises:
            FantasyAuthError: If the player page carries no ``<title>`` (a
                logged-out/redirected page), so a stale session surfaces as a
                clear auth error rather than an opaque ``IndexError``.
        """
        resp = self.write_session.get(
            f"https://sports.yahoo.com/nhl/players/{player_id}/"
        )
        # Player page title carries the name, e.g. "<title>Owen Nolan (...)".
        parts = resp.text.split("title>")
        if len(parts) < 2:
            raise FantasyAuthError(
                f"Failed to read player {player_id} via cookie (no page title; "
                "session may be stale). Check YAHOO_COOKIE."
            )
        name = parts[1].split("(")[0].strip()

        return AgnosticPlayer(
            player_id=player_id,
            name=PlayerName(full=name),
            position_type=PositionType.SKATER,
            eligible_positions=[Position.UTIL],
            status=PlayerStatus.ACTIVE,
            team=NhlTeam(name="", abbr="", team_id=0),
        )
