from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from fantasy_manager.model.enums.sport import Sport
from fantasy_manager.model.player import PlayerName


class GoalieConfidence(Enum):
    """DailyFaceoff's starting-goalie confidence tiers.

    The v1 JSON feed only exposes an *ordered* goalie list (projected starter
    first), never DailyFaceoff's Confirmed/Likely/Unconfirmed label, so every
    goalie parsed from the feed is ``UNCONFIRMED``. The richer labels require
    the direct-scrape fallback noted in ``client/news/dailyfaceoff.py``.
    """

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNCONFIRMED = "unconfirmed"


class InjuriesFreshness(Enum):
    """Freshness of the injury slice of the feed, mirroring ``injuries_meta``.

    Lines and injuries refresh independently: the lines can be current while
    the ESPN-sourced injuries are a preserved older copy, so this travels
    separately from the feed's top-level ``updated_at``.
    """

    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class GoalieSlot(BaseModel):
    """A goalie in a team's projected goalie slate.

    Attrs:
        goalie (PlayerName):            The goalie's identity.
        is_starter (bool):              True for the projected starter (first
                                        goalie listed in the feed).
        confidence (GoalieConfidence):  Always ``UNCONFIRMED`` from the v1 feed
                                        (see ``GoalieConfidence``).
    """

    goalie: PlayerName
    is_starter: bool = False
    confidence: GoalieConfidence = GoalieConfidence.UNCONFIRMED


class Injury(BaseModel):
    """An injured/unavailable player, as reported in the feed (ESPN-sourced).

    Attrs:
        player (PlayerName):          The injured player's identity.
        status (str):                 Raw status label (e.g. "Out",
                                      "Day-To-Day", "Injured Reserve").
        position (Optional[str]):     Position abbreviation, if reported.
        description (Optional[str]):   Free-text note about the injury, if any.
    """

    player: PlayerName
    status: str
    position: Optional[str] = None
    description: Optional[str] = None


class TeamLines(BaseModel):
    """Structured per-team line data parsed from the DailyFaceoff feed.

    ``forward_lines``, ``defense_pairs`` and ``power_play_units`` hold player
    identities in feed order (line 1 first, PP1 before PP2). ``penalty_kill_units``
    and ``scratches`` are always empty in v1 — the JSON feed does not carry
    special-teams PK usage or an explicit healthy-scratch list (see the module
    docstring in ``client/news/dailyfaceoff.py``). They exist so the shape stays
    forward-compatible with the diff/state work in issue #32.

    Attrs:
        team_slug (str):                        DailyFaceoff team slug, e.g.
                                                "anaheim-ducks".
        team_abbr (Optional[str]):              Standard NHL abbreviation (for
                                                the name-match team tiebreak).
        team_name (Optional[str]):              Human-readable team name.
        forward_lines (list[list[PlayerName]]): EV forward lines, line 1 first.
        defense_pairs (list[list[PlayerName]]): EV defense pairs, pair 1 first.
        goalies (list[GoalieSlot]):             Projected goalie slate, starter
                                                first.
        power_play_units (list[list[PlayerName]]): PP units, PP1 first.
        penalty_kill_units (list[list[PlayerName]]): Not in v1 feed; always [].
        injuries (list[Injury]):                Injured/unavailable players.
        scratches (list[PlayerName]):           Not in v1 feed; always [].
    """

    team_slug: str
    team_abbr: Optional[str] = None
    team_name: Optional[str] = None
    forward_lines: list[list[PlayerName]] = []
    defense_pairs: list[list[PlayerName]] = []
    goalies: list[GoalieSlot] = []
    power_play_units: list[list[PlayerName]] = []
    penalty_kill_units: list[list[PlayerName]] = []
    injuries: list[Injury] = []
    scratches: list[PlayerName] = []


class LinesFeed(BaseModel):
    """A parsed snapshot of the DailyFaceoff line-combinations feed.

    Attrs:
        source (str):                       Feed source identifier, e.g.
                                            "dailyfaceoff.com".
        updated_at (Optional[datetime]):    When the lines were last refreshed
                                            (UTC), if the feed reported it.
        teams (dict[str, TeamLines]):       Per-team lines, keyed by team slug.
        injuries_status (InjuriesFreshness): Freshness of the injury slice.
        injuries_updated_at (Optional[datetime]): When injuries last refreshed
                                            (UTC), if reported.
        sport (Sport):                      The sport the feed pertains to.
    """

    source: str
    updated_at: Optional[datetime] = None
    teams: dict[str, TeamLines] = {}
    injuries_status: InjuriesFreshness = InjuriesFreshness.UNAVAILABLE
    injuries_updated_at: Optional[datetime] = None
    sport: Sport = Sport.NHL
