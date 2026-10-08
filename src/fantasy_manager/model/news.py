from __future__ import annotations
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from fantasy_manager.model.enums.news_category import NewsCategory
from fantasy_manager.model.enums.news_severity import NewsSeverity
from fantasy_manager.model.enums.sport import Sport
from fantasy_manager.model.nhl_team import NhlTeam
from fantasy_manager.model.player import BasePlayer


class NewsItem(BaseModel):
    """A raw, normalized item fetched from a news source (e.g. a social post).

    Attrs:
        id (str):                        Source-scoped unique identifier for the item.
        source (str):                    Where the item came from (e.g. "dailyfaceoff").
        timestamp (datetime):            When the item was published.
        text (str):                      The raw text content of the item.
        url (Optional[str]):             Link back to the original item, if any.
        players (list[BasePlayer]):      Players mentioned in the item.
        sport (Sport):                   The sport the item pertains to.
    """

    id: str
    source: str
    timestamp: datetime
    text: str
    url: Optional[str] = None
    players: list[BasePlayer] = []
    sport: Sport = Sport.NHL


class PlayerNewsEvent(BaseModel):
    """A structured event derived from one or more NewsItems.

    Attrs:
        category (NewsCategory):          The kind of event (injury, lineup, etc.).
        players (list[BasePlayer]):       The players the event is primarily about.
        beneficiary (Optional[BasePlayer]): Player who benefits (e.g. promoted in the
                                          lineup when another player is scratched).
        team (Optional[NhlTeam]):         The NHL team the event concerns, if any.
        severity (NewsSeverity):          How impactful the event is.
        sport (Sport):                    The sport the event pertains to.
    """

    category: NewsCategory
    players: list[BasePlayer] = []
    beneficiary: Optional[BasePlayer] = None
    team: Optional[NhlTeam] = None
    severity: NewsSeverity = NewsSeverity.INFO
    sport: Sport = Sport.NHL
