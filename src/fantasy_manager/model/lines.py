from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel

from fantasy_manager.model.enums.sport import Sport
from fantasy_manager.model.player import PlayerName


class GoalieConfidence(Enum):
    """DailyFaceoff's starting-goalie confidence tiers.

    The line-combinations page only exposes an *ordered* goalie list (projected
    starter first), never DailyFaceoff's Confirmed/Likely/Unconfirmed label, so
    every goalie parsed from the feed is ``UNCONFIRMED``. The richer labels live
    on the separate starting-goalies page (see the module docstring in
    ``client/news/dailyfaceoff.py``).
    """

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNCONFIRMED = "unconfirmed"


class InjuriesFreshness(Enum):
    """Freshness of the injury slice of the feed.

    Injuries ship on the same line-combinations page as the lines, so they
    share the lines' refresh and this is ``FRESH`` whenever a team parses. It
    stays a separate field (rather than folding into the top-level
    ``updated_at``) so a future source that refreshes injuries independently can
    report it without a model change.
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
        confidence (GoalieConfidence):  Always ``UNCONFIRMED`` from the
                                        line-combinations page (see
                                        ``GoalieConfidence``).
    """

    goalie: PlayerName
    is_starter: bool = False
    confidence: GoalieConfidence = GoalieConfidence.UNCONFIRMED


class Injury(BaseModel):
    """An injured/unavailable player, from the page's off-ice (``oi``) list.

    Attrs:
        player (PlayerName):          The injured player's identity.
        status (str):                 Raw status label (e.g. "Out",
                                      "Day-To-Day", "Injured Reserve").
        position (Optional[str]):     Position abbreviation, if reported (the
                                      off-ice list does not carry it, so None).
        description (Optional[str]):   Free-text note about the injury, if any
                                      (not carried by the off-ice list, so None).
    """

    player: PlayerName
    status: str
    position: Optional[str] = None
    description: Optional[str] = None


class TeamLines(BaseModel):
    """Structured per-team line data parsed from the DailyFaceoff feed.

    ``forward_lines``, ``defense_pairs``, ``power_play_units`` and
    ``penalty_kill_units`` hold player identities in feed order (line 1 first,
    PP1 before PP2, PK1 before PK2). ``scratches`` is always empty — the
    off-ice list the feed carries is injured players only, with no explicit
    healthy-scratch list (see the module docstring in
    ``client/news/dailyfaceoff.py``). It exists so the shape stays
    forward-compatible with the diff/state work in issue #32.

    Attrs:
        team_slug (str):                        DailyFaceoff team slug, e.g.
                                                "anaheim-ducks".
        team_abbr (Optional[str]):              Standard NHL abbreviation (for
                                                the name-match team tiebreak).
        team_name (Optional[str]):              Human-readable team name.
        updated_at (Optional[datetime]):        When this team's lines were last
                                                refreshed (UTC), per the page.
        forward_lines (list[list[PlayerName]]): EV forward lines, line 1 first.
        defense_pairs (list[list[PlayerName]]): EV defense pairs, pair 1 first.
        goalies (list[GoalieSlot]):             Projected goalie slate, starter
                                                first.
        power_play_units (list[list[PlayerName]]): PP units, PP1 first.
        penalty_kill_units (list[list[PlayerName]]): PK units, PK1 first.
        injuries (list[Injury]):                Injured/unavailable players.
        scratches (list[PlayerName]):           Healthy scratches; not carried
                                                by the feed, so always [].
    """

    team_slug: str
    team_abbr: Optional[str] = None
    team_name: Optional[str] = None
    updated_at: Optional[datetime] = None
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
