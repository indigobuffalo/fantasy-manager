"""DailyFaceoff line-combinations source client.

Reads structured NHL line data directly from DailyFaceoff's own pages. Each
team's ``/teams/<slug>/line-combinations`` page is a Next.js app that embeds its
full data as JSON in a ``<script id="__NEXT_DATA__">`` tag; this client fetches
the page, extracts that blob, and parses ``props.pageProps.combinations`` — no
HTML layout scraping, just the data the page already ships.

History: v1 read a third-party mirror (the ``hg913488/nhl-line-combos-app``
feed) to avoid hitting DailyFaceoff directly. That mirror went dark (the app
repo is gone and the scraper stopped running), so this client now reads the
source the mirror itself scraped. The direct source is also *richer* than the
mirror was — it carries penalty-kill units and an injured list the mirror
dropped.

Per-team ``combinations`` payload (fields this client uses)::

    {
      "teamName": "Edmonton Oilers",
      "teamAbbreviation": "EDM",
      "teamSlug": "edmonton-oilers",
      "updatedAt": "2026-10-23T14:07:18.977Z",      # ISO-8601 UTC
      "players": [
        {
          "name": "Connor McDavid",
          "categoryIdentifier": "ev",    # ev | pp | pk | oi
          "groupIdentifier":    "f1",    # f1-f4, d1-d4, g | pp1/pp2 | pk1/pk2 | ir
          "positionIdentifier": "c",     # lw/c/rw, ld/rd, g1/g2 | sk1-sk5 | ir1..
          "injuryStatus":       null,    # ir | out | dtd (on the oi list)
          ...
        }, ...
      ]
    }

Categories map onto the model as:
    - ``ev`` groups ``f1..f4`` -> ``forward_lines`` (line 1 first)
    - ``ev`` groups ``d1..d4`` -> ``defense_pairs`` (pair 1 first)
    - ``ev`` group  ``g``      -> ``goalies`` (``g1`` is the projected starter)
    - ``pp`` groups ``pp1/pp2``-> ``power_play_units`` (PP1 first)
    - ``pk`` groups ``pk1/pk2``-> ``penalty_kill_units`` (PK1 first)
    - ``oi`` (off ice)         -> ``injuries`` (status from ``injuryStatus``)

What the page does NOT give, so it stays empty/flat in the model:
    - DailyFaceoff's Confirmed/Likely/Unconfirmed goalie labels (the page only
      orders goalies by ``g1``/``g2``; everything parses as ``UNCONFIRMED`` —
      the labels live on the separate starting-goalies page)
    - an explicit *healthy*-scratch list distinct from injuries (the off-ice
      list is injured players only), so ``scratches`` stays empty

Requests MUST send a browser-like ``User-Agent``; without one DailyFaceoff's
edge returns ``403``. No cookies or auth are needed.

Player names are mapped to the project's ``PlayerName`` identity (accent-stripped
last name + first initial), consistent with the ``get-yahoo-player-id`` matching
rules; the diff/resolution against real fantasy player ids lands in issue #32.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import requests
from requests import Session

from fantasy_manager.exceptions import NewsSourceUnavailableError
from fantasy_manager.model.lines import (
    GoalieSlot,
    Injury,
    InjuriesFreshness,
    LinesFeed,
    TeamLines,
)
from fantasy_manager.model.player import PlayerName


logger = logging.getLogger(__name__)


SOURCE = "dailyfaceoff.com"

# DailyFaceoff's site. Each team's line-combinations page embeds the data as
# JSON; we fetch the page and pull the embedded blob out (see _extract_*).
BASE_URL = "https://www.dailyfaceoff.com"
TEAM_PATH_TEMPLATE = "/teams/{slug}/line-combinations"

# The Next.js data blob lives in this script tag; the group(1) is raw JSON.
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)

# A browser-like UA is REQUIRED — a missing/non-browser UA gets a 403 from the
# site's edge. No cookies/auth are needed beyond this.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# DailyFaceoff refreshes lines several times a day; anything older than this is
# treated as stale (logged, but still returned — see module docstring).
DEFAULT_STALE_AFTER = timedelta(hours=36)

# How long to wait on a single team page before giving up.
DEFAULT_TIMEOUT_SECONDS = 15

# A full-league pull fetches 32 independent pages; do so concurrently. The cap
# keeps us polite to the site while cutting wall-clock from ~sum to ~max.
DEFAULT_MAX_WORKERS = 8

# The 32 NHL team slugs DailyFaceoff publishes line-combinations pages for. The
# page itself carries each team's abbreviation and name, so this is only the
# work-list of pages to fetch for a full-league pull.
TEAM_SLUGS: tuple[str, ...] = (
    "anaheim-ducks",
    "boston-bruins",
    "buffalo-sabres",
    "calgary-flames",
    "carolina-hurricanes",
    "chicago-blackhawks",
    "colorado-avalanche",
    "columbus-blue-jackets",
    "dallas-stars",
    "detroit-red-wings",
    "edmonton-oilers",
    "florida-panthers",
    "los-angeles-kings",
    "minnesota-wild",
    "montreal-canadiens",
    "nashville-predators",
    "new-jersey-devils",
    "new-york-islanders",
    "new-york-rangers",
    "ottawa-senators",
    "philadelphia-flyers",
    "pittsburgh-penguins",
    "san-jose-sharks",
    "seattle-kraken",
    "st-louis-blues",
    "tampa-bay-lightning",
    "toronto-maple-leafs",
    "utah-mammoth",
    "vancouver-canucks",
    "vegas-golden-knights",
    "washington-capitals",
    "winnipeg-jets",
)

# Category identifiers on each player entry.
_CAT_EVEN_STRENGTH = "ev"
_CAT_POWER_PLAY = "pp"
_CAT_PENALTY_KILL = "pk"
_CAT_OFF_ICE = "oi"

# Within an even-strength group the skaters carry role identifiers (not numbers);
# this fixes their left-to-right order. Numbered slots (sk1.., g1/g2) sort by
# their trailing number instead (see _position_sort_key).
_EV_ROLE_ORDER = {"lw": 0, "c": 1, "rw": 2, "ld": 0, "rd": 1}


def _strip_accents(value: str) -> str:
    """Accent-strip and lowercase, matching get-yahoo-player-id's ``strip``.

    E.g. "Stützle" -> "stutzle", "Nečas" -> "necas". Used for the identity
    fields the diff/resolution step (issue #32) matches on.
    """
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def parse_player_name(raw: str) -> PlayerName:
    """Parse a feed name (e.g. "Ukko-Pekka Luukkonen") into a ``PlayerName``.

    The last whitespace-delimited token is the surname and the first is the
    given name — the same split get-yahoo-player-id uses — so multi-word
    surnames collapse to their final token (consistent, if imperfect). ``full``
    is title-cased for display; ``ascii_first``/``ascii_last`` are accent-
    stripped and lowercased for matching.
    """
    full = " ".join(raw.split())  # collapse stray whitespace
    tokens = full.split(" ")
    first = tokens[0] if tokens else ""
    last = tokens[-1] if len(tokens) > 1 else ""
    return PlayerName(
        full=full.title(),
        first=first.title() or None,
        last=last.title() or None,
        ascii_first=_strip_accents(first) or None,
        ascii_last=_strip_accents(last) or None,
    )


def _parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 feed timestamp into a UTC-aware datetime, or None.

    The page stamps times like ``2026-10-23T14:07:18.977Z``; a naive or
    offset value is normalized to UTC.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Unparseable feed timestamp: %r", value)
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _position_sort_key(position_id: Optional[str]) -> tuple[int, int]:
    """Order players within a group.

    Numbered slots (``sk1``, ``g2``, ...) sort by their trailing number; the
    even-strength role identifiers (``lw``/``c``/``rw``, ``ld``/``rd``) fall back
    to a fixed left-to-right order. A group only ever mixes one scheme.
    """
    pid = position_id or ""
    match = re.search(r"(\d+)$", pid)
    if match:
        return (0, int(match.group(1)))
    return (1, _EV_ROLE_ORDER.get(pid, 99))


def _group_sort_key(group_id: Optional[str]) -> int:
    """Order groups by their trailing number: f1<f2<f3<f4, pp1<pp2, pk1<pk2."""
    match = re.search(r"(\d+)$", group_id or "")
    return int(match.group(1)) if match else 0


def _players_in_category(players: list[dict], category: str) -> dict[str, list[dict]]:
    """Bucket a category's players by their ``groupIdentifier``, in page order."""
    groups: dict[str, list[dict]] = {}
    for player in players:
        if not isinstance(player, dict):
            continue
        if player.get("categoryIdentifier") != category:
            continue
        group_id = player.get("groupIdentifier")
        if not isinstance(group_id, str):
            continue
        groups.setdefault(group_id, []).append(player)
    return groups


def _units_from_groups(
    groups: dict[str, list[dict]], prefix: str
) -> list[list[PlayerName]]:
    """Build ordered units from groups whose id starts with ``prefix``.

    Groups are ordered by their trailing number (line 1 first); players within a
    unit are ordered by :func:`_position_sort_key`. Empty units are dropped.
    """
    units: list[list[PlayerName]] = []
    group_ids = sorted(
        (gid for gid in groups if gid.startswith(prefix)), key=_group_sort_key
    )
    for group_id in group_ids:
        members = sorted(
            groups[group_id],
            key=lambda p: _position_sort_key(p.get("positionIdentifier")),
        )
        names = [parse_player_name(p["name"]) for p in members if p.get("name")]
        if names:
            units.append(names)
    return units


def _parse_goalies(even_strength: dict[str, list[dict]]) -> list[GoalieSlot]:
    """Parse the goalie group; ``g1`` (else the first listed) is the starter.

    Confidence is always UNCONFIRMED — the line-combinations page only orders
    goalies, it carries no Confirmed/Likely label (see the module docstring).
    """
    goalies = sorted(
        even_strength.get("g", []),
        key=lambda p: _position_sort_key(p.get("positionIdentifier")),
    )
    slots = [
        GoalieSlot(
            goalie=parse_player_name(p["name"]),
            is_starter=(p.get("positionIdentifier") == "g1"),
        )
        for p in goalies
        if p.get("name")
    ]
    if slots and not any(slot.is_starter for slot in slots):
        slots[0].is_starter = True
    return slots


def _parse_injuries(players: list[dict]) -> list[Injury]:
    """Parse the off-ice (``oi``) list into injuries.

    The off-ice list is injured players only (IR/Out/Day-to-Day); ``injuryStatus``
    is the raw label. Position/description aren't carried on this list.
    """
    injuries: list[Injury] = []
    for player in players:
        if not isinstance(player, dict):
            continue
        if player.get("categoryIdentifier") != _CAT_OFF_ICE:
            continue
        name = player.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        injuries.append(
            Injury(
                player=parse_player_name(name),
                status=(player.get("injuryStatus") or "Unknown"),
            )
        )
    return injuries


class DailyFaceoffClient:
    """Fetches and parses DailyFaceoff's line-combinations pages."""

    def __init__(
        self,
        session: Optional[Session] = None,
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
        user_agent: str = DEFAULT_USER_AGENT,
        max_workers: int = DEFAULT_MAX_WORKERS,
    ):
        self.session = session or requests.Session()
        # A browser-like UA is mandatory (see DEFAULT_USER_AGENT). requests.Session
        # pre-sets its own ``python-requests/<ver>`` UA (which earns a 403), so
        # replace that — but keep a genuinely custom UA a caller chose.
        current_ua = self.session.headers.get("User-Agent", "")
        if not current_ua or current_ua.startswith("python-requests"):
            self.session.headers["User-Agent"] = user_agent
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.stale_after = stale_after
        self.max_workers = max_workers

    def team_url(self, slug: str) -> str:
        """The line-combinations page URL for a team slug."""
        return f"{self.base_url}{TEAM_PATH_TEMPLATE.format(slug=slug)}"

    def fetch_lines(self, slugs: Optional[Iterable[str]] = None) -> LinesFeed:
        """Fetch and parse line combinations for ``slugs`` (default: all teams).

        The teams are independent pages, so they're fetched concurrently (bounded
        by ``max_workers``). A team whose page can't be fetched or parsed is
        logged and skipped rather than failing the whole pull. If no team could
        be fetched at all, the source is treated as unavailable.

        Raises:
            NewsSourceUnavailableError: if not a single team could be read.

        A stale-but-parseable result is returned (with a warning), not an error,
        so callers can still act on last-known lines.
        """
        slugs = list(slugs) if slugs is not None else list(TEAM_SLUGS)
        workers = max(1, min(self.max_workers, len(slugs)))
        # ThreadPoolExecutor.map preserves input order, so `teams` stays ordered
        # by `slugs`. The shared Session is safe here: requests/urllib3 pool
        # connections across threads for plain concurrent GETs.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = pool.map(self._fetch_team_or_none, slugs)

        teams: dict[str, TeamLines] = {}
        failures: list[str] = []
        for slug, team in zip(slugs, results):
            if team is None:
                failures.append(slug)
            else:
                teams[slug] = team

        if not teams:
            raise NewsSourceUnavailableError(
                SOURCE, f"no teams could be fetched ({len(failures)} failed)"
            )
        if failures:
            logger.warning(
                "DailyFaceoff: %d/%d teams failed: %s",
                len(failures),
                len(slugs),
                ", ".join(failures),
            )

        timestamps = [t.updated_at for t in teams.values() if t.updated_at]
        newest = max(timestamps) if timestamps else None
        feed = LinesFeed(
            source=SOURCE,
            updated_at=newest,
            teams=teams,
            # Injuries ship on the same page as the lines, so they share freshness.
            injuries_status=InjuriesFreshness.FRESH,
            injuries_updated_at=newest,
        )
        if self.is_stale(feed):
            logger.warning(
                "DailyFaceoff lines are stale (newest updated_at=%s); serving "
                "last-known data.",
                newest,
            )
        return feed

    def fetch_team(self, slug: str) -> TeamLines:
        """Fetch and parse a single team's line-combinations page.

        Raises:
            NewsSourceUnavailableError: if the page can't be fetched or parsed.
        """
        html = self._get_html(self.team_url(slug))
        return self.parse_team(self._extract_combinations(html))

    def _fetch_team_or_none(self, slug: str) -> Optional[TeamLines]:
        """Fetch one team, logging and swallowing a source error as ``None``.

        Used by the concurrent :meth:`fetch_lines` so one bad page doesn't sink
        the whole pull.
        """
        try:
            return self.fetch_team(slug)
        except NewsSourceUnavailableError as exc:
            logger.warning("DailyFaceoff: skipping %s (%s)", slug, exc)
            return None

    def _get_html(self, url: str) -> str:
        """GET a page as text, mapping network/HTTP failures to a source error."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            raise NewsSourceUnavailableError(
                SOURCE, f"could not fetch {url}: {exc}"
            ) from exc

    def is_stale(self, feed: LinesFeed, now: Optional[datetime] = None) -> bool:
        """Whether the feed's lines are older than ``stale_after``.

        A feed with no ``updated_at`` is treated as stale (we can't prove it
        fresh).
        """
        if feed.updated_at is None:
            return True
        now = now or datetime.now(timezone.utc)
        return (now - feed.updated_at) > self.stale_after

    @staticmethod
    def _extract_combinations(html: str) -> dict:
        """Pull ``props.pageProps.combinations`` out of a page's __NEXT_DATA__."""
        match = _NEXT_DATA_RE.search(html)
        if not match:
            raise NewsSourceUnavailableError(
                SOURCE, "could not find __NEXT_DATA__ in page"
            )
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError) as exc:
            raise NewsSourceUnavailableError(
                SOURCE, f"__NEXT_DATA__ was not valid JSON: {exc}"
            ) from exc
        page_props = (data.get("props") or {}).get("pageProps") or {}
        combinations = page_props.get("combinations")
        if not isinstance(combinations, dict):
            raise NewsSourceUnavailableError(
                SOURCE, "page had no line-combinations data"
            )
        return combinations

    @staticmethod
    def parse_team(combinations: dict) -> TeamLines:
        """Parse one team's ``combinations`` payload into ``TeamLines``.

        Tolerant of missing optional groups (a team with no PK listed just gets
        empty ``penalty_kill_units``, etc.).
        """
        if not isinstance(combinations, dict):
            raise NewsSourceUnavailableError(
                SOURCE,
                f"expected a combinations object, got {type(combinations).__name__}",
            )
        players = combinations.get("players")
        if not isinstance(players, list):
            raise NewsSourceUnavailableError(
                SOURCE, "combinations payload is missing a 'players' list"
            )

        even_strength = _players_in_category(players, _CAT_EVEN_STRENGTH)
        power_play = _players_in_category(players, _CAT_POWER_PLAY)
        penalty_kill = _players_in_category(players, _CAT_PENALTY_KILL)

        return TeamLines(
            team_slug=combinations.get("teamSlug") or "",
            team_abbr=combinations.get("teamAbbreviation") or None,
            team_name=combinations.get("teamName") or None,
            updated_at=_parse_iso_timestamp(combinations.get("updatedAt")),
            forward_lines=_units_from_groups(even_strength, "f"),
            defense_pairs=_units_from_groups(even_strength, "d"),
            goalies=_parse_goalies(even_strength),
            power_play_units=_units_from_groups(power_play, "pp"),
            penalty_kill_units=_units_from_groups(penalty_kill, "pk"),
            # scratches: the off-ice list is injuries only (see docstring).
            injuries=_parse_injuries(players),
        )
