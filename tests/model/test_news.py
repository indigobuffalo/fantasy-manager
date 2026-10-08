from datetime import datetime

import pytest
from hamcrest import assert_that, contains_exactly, empty, equal_to, is_, none
from pydantic import ValidationError

from fantasy_manager.model.enums.news_category import NewsCategory
from fantasy_manager.model.enums.news_severity import NewsSeverity
from fantasy_manager.model.enums.sport import Sport
from fantasy_manager.model.news import NewsItem, PlayerNewsEvent
from fantasy_manager.model.nhl_team import NhlTeam
from fantasy_manager.model.player import BasePlayer, PlayerName


PLAYER_ONE = BasePlayer(
    player_id=1,
    name=PlayerName(first="Owen", last="Nolan", full="Owen Nolan"),
)


PLAYER_TWO = BasePlayer(
    player_id=2,
    name=PlayerName(first="Joe", last="Pavelski", full="Joe Pavelski"),
)


SHARKS = NhlTeam(name="San Jose Sharks", abbr="SJS", team_id=28)


TIMESTAMP = datetime(2026, 1, 1, 12, 0, 0)


def test_news_item_constructs_with_all_fields():
    item = NewsItem(
        id="abc-123",
        source="dailyfaceoff",
        timestamp=TIMESTAMP,
        text="Nolan returns to the lineup.",
        url="https://example.com/abc-123",
        players=[PLAYER_ONE],
        sport=Sport.NHL,
    )

    assert_that(item.id, equal_to("abc-123"))
    assert_that(item.source, equal_to("dailyfaceoff"))
    assert_that(item.timestamp, equal_to(TIMESTAMP))
    assert_that(item.players, contains_exactly(PLAYER_ONE))
    assert_that(item.sport, equal_to(Sport.NHL))


def test_news_item_defaults():
    item = NewsItem(
        id="abc-123",
        source="dailyfaceoff",
        timestamp=TIMESTAMP,
        text="No players tagged yet.",
    )

    assert_that(item.url, is_(none()))
    assert_that(item.players, is_(empty()))
    assert_that(item.sport, equal_to(Sport.NHL))


def test_news_item_requires_core_fields():
    with pytest.raises(ValidationError):
        NewsItem(source="dailyfaceoff", timestamp=TIMESTAMP, text="missing id")


def test_player_news_event_constructs_with_all_fields():
    event = PlayerNewsEvent(
        category=NewsCategory.SCRATCH,
        players=[PLAYER_ONE],
        beneficiary=PLAYER_TWO,
        team=SHARKS,
        severity=NewsSeverity.MAJOR,
    )

    assert_that(event.category, equal_to(NewsCategory.SCRATCH))
    assert_that(event.players, contains_exactly(PLAYER_ONE))
    assert_that(event.beneficiary, equal_to(PLAYER_TWO))
    assert_that(event.team, equal_to(SHARKS))
    assert_that(event.severity, equal_to(NewsSeverity.MAJOR))
    assert_that(event.sport, equal_to(Sport.NHL))


def test_player_news_event_defaults():
    event = PlayerNewsEvent(category=NewsCategory.OTHER)

    assert_that(event.players, is_(empty()))
    assert_that(event.beneficiary, is_(none()))
    assert_that(event.team, is_(none()))
    assert_that(event.severity, equal_to(NewsSeverity.INFO))
    assert_that(event.sport, equal_to(Sport.NHL))


def test_player_news_event_requires_category():
    with pytest.raises(ValidationError):
        PlayerNewsEvent(players=[PLAYER_ONE])


def test_player_news_event_rejects_invalid_category():
    with pytest.raises(ValidationError):
        PlayerNewsEvent(category="not-a-category")
