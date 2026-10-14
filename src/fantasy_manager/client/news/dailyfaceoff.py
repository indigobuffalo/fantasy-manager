"""DailyFaceoff line-combinations source client.

Pulls structured NHL line data **without scraping** in v1. Instead of hitting
DailyFaceoff's HTML directly, this reads the public, auto-updated JSON mirror
maintained by the ``hg913488/nhl-line-combos`` project, which scrapes
DailyFaceoff (lines + PP units) and ESPN (injuries) once a day and commits the
result to ``data/lines.json``.

Feed shape (current scraper output)::

    {
      "source": "dailyfaceoff.com",
      "updated_at": "2026-03-02 16:34:05 UTC",
      "teams": {
        "<team-slug>": {
          "forwards": [[name, name, name], ...],   # EV lines, line 1 first
          "defense":  [[name, name], ...],         # EV pairs, pair 1 first
          "goalies":  [[name], [name]],            # ordered, starter first
          "pp1":      [name, ...],                  # power-play unit 1
          "pp2":      [name, ...]                   # power-play unit 2
        }, ...
      },
      "injuries": {
        "<team-slug>": [{"name", "pos", "status", "desc"}, ...]
      },
      "injuries_meta": {"source", "status": fresh|stale|unavailable, "updated_at"}
    }

Older snapshots omit ``pp1``/``pp2``/``injuries``; parsing tolerates their
absence (the corresponding fields come back empty).

What the feed does NOT carry, and so stays empty in v1:
    - penalty-kill (PK) units
    - DailyFaceoff's Confirmed/Likely/Unconfirmed goalie labels (the feed only
      orders goalies; everything parses as ``UNCONFIRMED``)
    - an explicit healthy-scratch list

**Fallback (future work, not v1):** if this mirror goes stale or disappears, or
the PK/goalie-confidence/scratch data becomes required, scrape DailyFaceoff's
team ``/line-combinations`` pages directly — each embeds a ``__NEXT_DATA__``
``<script>`` with the same ``categoryIdentifier``/``groupIdentifier`` structure
the mirror's scraper parses, plus the goalie-confidence label and PK groups.

Player names are mapped to the project's ``PlayerName`` identity (accent-stripped
last name + first initial), consistent with the ``get-yahoo-player-id`` matching
rules; the diff/resolution against real fantasy player ids lands in issue #32.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

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

# Public auto-updated JSON mirror of DailyFaceoff lines (+ ESPN injuries).
FEED_URL = (
    "https://raw.githubusercontent.com/hg913488/nhl-line-combos/main/data/lines.json"
)

# The mirror refreshes roughly once a day; anything older than this is treated
# as stale (logged, but still returned — see module docstring).
DEFAULT_STALE_AFTER = timedelta(hours=36)

# How long to wait on the feed before giving up.
DEFAULT_TIMEOUT_SECONDS = 15

# Timestamps in the feed look like "2026-03-02 16:34:05 UTC" (always UTC).
_FEED_TIME_FORMAT = "%Y-%m-%d %H:%M:%S UTC"

# DailyFaceoff team slug -> (standard NHL abbreviation, display name). The abbr
# is what the name-match team tiebreak keys on (see get-yahoo-player-id). The
# feed has no team ids, so a full NhlTeam (which requires one) is intentionally
# not built here; a later issue can resolve it via the NHL client if needed.
_SLUG_TO_TEAM: dict[str, tuple[str, str]] = {
    "anaheim-ducks": ("ANA", "Anaheim Ducks"),
    "boston-bruins": ("BOS", "Boston Bruins"),
    "buffalo-sabres": ("BUF", "Buffalo Sabres"),
    "calgary-flames": ("CGY", "Calgary Flames"),
    "carolina-hurricanes": ("CAR", "Carolina Hurricanes"),
    "chicago-blackhawks": ("CHI", "Chicago Blackhawks"),
    "colorado-avalanche": ("COL", "Colorado Avalanche"),
    "columbus-blue-jackets": ("CBJ", "Columbus Blue Jackets"),
    "dallas-stars": ("DAL", "Dallas Stars"),
    "detroit-red-wings": ("DET", "Detroit Red Wings"),
    "edmonton-oilers": ("EDM", "Edmonton Oilers"),
    "florida-panthers": ("FLA", "Florida Panthers"),
    "los-angeles-kings": ("LAK", "Los Angeles Kings"),
    "minnesota-wild": ("MIN", "Minnesota Wild"),
    "montreal-canadiens": ("MTL", "Montreal Canadiens"),
    "nashville-predators": ("NSH", "Nashville Predators"),
    "new-jersey-devils": ("NJD", "New Jersey Devils"),
    "new-york-islanders": ("NYI", "New York Islanders"),
    "new-york-rangers": ("NYR", "New York Rangers"),
    "ottawa-senators": ("OTT", "Ottawa Senators"),
    "philadelphia-flyers": ("PHI", "Philadelphia Flyers"),
    "pittsburgh-penguins": ("PIT", "Pittsburgh Penguins"),
    "san-jose-sharks": ("SJS", "San Jose Sharks"),
    "seattle-kraken": ("SEA", "Seattle Kraken"),
    "st-louis-blues": ("STL", "St. Louis Blues"),
    "tampa-bay-lightning": ("TBL", "Tampa Bay Lightning"),
    "toronto-maple-leafs": ("TOR", "Toronto Maple Leafs"),
    "utah-mammoth": ("UTA", "Utah Mammoth"),
    "vancouver-canucks": ("VAN", "Vancouver Canucks"),
    "vegas-golden-knights": ("VGK", "Vegas Golden Knights"),
    "washington-capitals": ("WSH", "Washington Capitals"),
    "winnipeg-jets": ("WPG", "Winnipeg Jets"),
}


def _strip_accents(value: str) -> str:
    """Accent-strip and lowercase, matching get-yahoo-player-id's ``strip``.

    E.g. "Stützle" -> "stutzle", "Nečas" -> "necas". Used for the identity
    fields the diff/resolution step (issue #32) matches on.
    """
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").lower()


def parse_player_name(raw: str) -> PlayerName:
    """Parse a feed name (e.g. "UKKO-PEKKA LUUKKONEN") into a ``PlayerName``.

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


def _parse_feed_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse a feed timestamp into a UTC-aware datetime, or None if unusable."""
    if not value:
        return None
    try:
        naive = datetime.strptime(value, _FEED_TIME_FORMAT)
    except (ValueError, TypeError):
        logger.warning("Unparseable feed timestamp: %r", value)
        return None
    return naive.replace(tzinfo=timezone.utc)


def _as_names(raw_names) -> list[PlayerName]:
    """Map a list of raw name strings to ``PlayerName`` identities."""
    if not isinstance(raw_names, list):
        return []
    return [parse_player_name(n) for n in raw_names if isinstance(n, str) and n.strip()]


def _parse_goalies(raw_goalies) -> list[GoalieSlot]:
    """Parse the ordered goalie list; the first goalie is the projected starter.

    The feed nests each goalie in a single-element list (``[["A"], ["B"]]``) but
    bare strings are tolerated too. Confidence is always UNCONFIRMED (the feed
    carries no label — see the module docstring).
    """
    slots: list[GoalieSlot] = []
    if not isinstance(raw_goalies, list):
        return slots
    for entry in raw_goalies:
        if isinstance(entry, list):
            names = [n for n in entry if isinstance(n, str) and n.strip()]
        elif isinstance(entry, str) and entry.strip():
            names = [entry]
        else:
            names = []
        for name in names:
            slots.append(
                GoalieSlot(
                    goalie=parse_player_name(name),
                    is_starter=not slots,  # first parsed goalie starts
                )
            )
    return slots


def _parse_injuries(raw_injuries) -> list[Injury]:
    """Parse a team's injury entries ({name, pos, status, desc})."""
    injuries: list[Injury] = []
    if not isinstance(raw_injuries, list):
        return injuries
    for entry in raw_injuries:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        injuries.append(
            Injury(
                player=parse_player_name(name),
                status=(entry.get("status") or "Unknown"),
                position=(entry.get("pos") or None),
                description=(entry.get("desc") or None),
            )
        )
    return injuries


class DailyFaceoffClient:
    """Fetches and parses the DailyFaceoff line-combinations JSON feed."""

    def __init__(
        self,
        session: Optional[Session] = None,
        feed_url: str = FEED_URL,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        stale_after: timedelta = DEFAULT_STALE_AFTER,
    ):
        self.session = session or requests.Session()
        self.feed_url = feed_url
        self.timeout = timeout
        self.stale_after = stale_after

    def fetch_lines(self) -> LinesFeed:
        """Fetch and parse the feed into a ``LinesFeed``.

        Raises:
            NewsSourceUnavailableError: if the feed can't be reached or parsed.

        A stale-but-parseable feed is returned (with a warning), not an error,
        so callers can still act on last-known lines.
        """
        feed = self.parse(self._get_raw())
        if self.is_stale(feed):
            logger.warning(
                "DailyFaceoff feed is stale (updated_at=%s); serving last-known "
                "data. Fallback would be a direct DailyFaceoff scrape.",
                feed.updated_at,
            )
        return feed

    def _get_raw(self) -> dict:
        """GET the feed and decode JSON, mapping failures to a source error."""
        try:
            resp = self.session.get(self.feed_url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            # Network/HTTP failure: the fallback (future work) is to scrape
            # DailyFaceoff's team pages directly — see the module docstring.
            raise NewsSourceUnavailableError(
                SOURCE, f"could not fetch feed: {exc}"
            ) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise NewsSourceUnavailableError(
                SOURCE, f"feed returned malformed JSON: {exc}"
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
    def parse(raw: dict) -> LinesFeed:
        """Parse a raw feed payload into a ``LinesFeed``.

        Tolerant of missing optional fields (older snapshots omit
        ``pp1``/``pp2``/``injuries``); unknown teams still parse.
        """
        if not isinstance(raw, dict):
            raise NewsSourceUnavailableError(
                SOURCE, f"expected a JSON object, got {type(raw).__name__}"
            )

        raw_teams = raw.get("teams")
        if not isinstance(raw_teams, dict):
            raise NewsSourceUnavailableError(SOURCE, "feed is missing a 'teams' object")

        raw_injuries = raw.get("injuries") or {}
        if not isinstance(raw_injuries, dict):
            raw_injuries = {}

        teams: dict[str, TeamLines] = {}
        for slug, data in raw_teams.items():
            if not isinstance(data, dict):
                continue
            abbr_name = _SLUG_TO_TEAM.get(slug)
            power_play_units = [
                unit
                for unit in (_as_names(data.get("pp1")), _as_names(data.get("pp2")))
                if unit
            ]
            teams[slug] = TeamLines(
                team_slug=slug,
                team_abbr=abbr_name[0] if abbr_name else None,
                team_name=abbr_name[1] if abbr_name else None,
                forward_lines=[
                    _as_names(line) for line in (data.get("forwards") or [])
                ],
                defense_pairs=[_as_names(pair) for pair in (data.get("defense") or [])],
                goalies=_parse_goalies(data.get("goalies")),
                power_play_units=power_play_units,
                # penalty_kill_units / scratches: not carried by the feed (v1).
                injuries=_parse_injuries(raw_injuries.get(slug)),
            )

        meta = raw.get("injuries_meta") or {}
        injuries_status = InjuriesFreshness.UNAVAILABLE
        if isinstance(meta, dict):
            try:
                injuries_status = InjuriesFreshness(meta.get("status"))
            except ValueError:
                injuries_status = InjuriesFreshness.UNAVAILABLE

        return LinesFeed(
            source=raw.get("source") or SOURCE,
            updated_at=_parse_feed_timestamp(raw.get("updated_at")),
            teams=teams,
            injuries_status=injuries_status,
            injuries_updated_at=_parse_feed_timestamp(
                meta.get("updated_at") if isinstance(meta, dict) else None
            ),
        )
