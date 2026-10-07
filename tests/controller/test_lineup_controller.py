from datetime import date, datetime
from unittest.mock import Mock
import zoneinfo

import pytest

import fantasy_manager
from fantasy_manager.service.lineup import LineupService
from fantasy_manager.controller.lineup import LineupController


CHANGES = [{"player_id": 1, "position": "RW"}]
LINEUP_DATE = "2026-01-15"
START_STR = "2026-01-15T01:35:00-08:00"
START_DT = datetime.fromisoformat(START_STR)
NEXT_MIDNIGHT = datetime(
    2026, 1, 16, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Pacific")
)


@pytest.fixture
def controller():
    yield LineupController(Mock(spec=LineupService))


@pytest.fixture
def mock_service(controller):
    yield controller.service


@pytest.fixture
def mock_get_start_fixed(monkeypatch):
    monkeypatch.setattr(
        fantasy_manager.controller.lineup, "get_start", lambda _: START_DT
    )


@pytest.fixture
def mock_get_start_midnight(monkeypatch):
    monkeypatch.setattr(
        fantasy_manager.controller.lineup, "get_start", lambda _: NEXT_MIDNIGHT
    )


def test_set_lineup(controller, mock_service, mock_get_start_fixed):
    controller.set_lineup(
        position_changes=CHANGES, lineup_date=LINEUP_DATE, start=START_STR
    )
    mock_service.set_lineup.assert_called_once_with(
        position_changes=CHANGES, lineup_date=date(2026, 1, 15), start=START_DT
    )


def test_set_lineup_no_start(controller, mock_service, mock_get_start_midnight):
    controller.set_lineup(position_changes=CHANGES, lineup_date=LINEUP_DATE)
    mock_service.set_lineup.assert_called_once_with(
        position_changes=CHANGES, lineup_date=date(2026, 1, 15), start=NEXT_MIDNIGHT
    )
