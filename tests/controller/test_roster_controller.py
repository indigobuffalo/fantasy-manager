from datetime import datetime
from unittest.mock import Mock
import zoneinfo

import pytest

import fantasy_manager
from fantasy_manager.service.roster import RosterService
from fantasy_manager.controller.roster import RosterController


ADD_ID = 123
DROP_ID = 456
FAAB = 99
START_STR = "2025-01-28T23:59:30-08:00"
START_DT = datetime.fromisoformat(START_STR)

ONE_AM_PAC = datetime(2025, 1, 2, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Pacific"))
NEXT_MIDNIGHT = datetime(
    2025, 1, 3, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Pacific")
)


@pytest.fixture
def controller():
    mock_roster_service = Mock(spec=RosterService)
    yield RosterController(mock_roster_service)


@pytest.fixture
def mock_service(controller):
    yield controller.service


@pytest.fixture
def mock_get_start_fixed(monkeypatch):
    monkeypatch.setattr(
        fantasy_manager.controller.roster, "get_start", lambda _: START_DT
    )


@pytest.fixture
def mock_get_start_midnight(monkeypatch):
    monkeypatch.setattr(
        fantasy_manager.controller.roster, "get_start", lambda _: NEXT_MIDNIGHT
    )


def test_add_player(controller, mock_service, mock_get_start_fixed):
    controller.add_player(ADD_ID, START_STR)
    mock_service.add_player.assert_called_once_with(add_id=ADD_ID, start=START_DT)


def test_add_player_no_start(controller, mock_service, mock_get_start_midnight):
    controller.add_player(ADD_ID)
    mock_service.add_player.assert_called_once_with(add_id=ADD_ID, start=NEXT_MIDNIGHT)


def test_replace_player(controller, mock_service, mock_get_start_fixed):
    controller.replace_player(add_id=ADD_ID, drop_id=DROP_ID, start=START_STR)
    mock_service.replace_player.assert_called_once_with(
        add_id=ADD_ID, drop_id=DROP_ID, start=START_DT
    )


def test_replace_player_no_start(controller, mock_service, mock_get_start_midnight):
    controller.replace_player(add_id=ADD_ID, drop_id=DROP_ID)
    mock_service.replace_player.assert_called_once_with(
        add_id=ADD_ID, drop_id=DROP_ID, start=NEXT_MIDNIGHT
    )


def test_add_player_claim(controller, mock_service, mock_get_start_fixed):
    controller.add_player_claim(add_id=ADD_ID, faab=FAAB, start=START_STR)
    mock_service.add_player_claim.assert_called_once_with(
        add_id=ADD_ID, faab=FAAB, start=START_DT
    )


def test_add_player_claim_no_start(controller, mock_service, mock_get_start_midnight):
    controller.add_player_claim(ADD_ID, faab=FAAB)
    mock_service.add_player_claim.assert_called_once_with(
        add_id=ADD_ID, faab=FAAB, start=NEXT_MIDNIGHT
    )


def test_replace_player_claim(controller, mock_service, mock_get_start_fixed):
    controller.replace_player_claim(
        add_id=ADD_ID, drop_id=DROP_ID, faab=FAAB, start=START_STR
    )
    mock_service.replace_player_claim.assert_called_once_with(
        add_id=ADD_ID, drop_id=DROP_ID, faab=FAAB, start=START_DT
    )


def test_replace_player_claim_no_start(
    controller, mock_service, mock_get_start_midnight
):
    controller.replace_player_claim(add_id=ADD_ID, drop_id=DROP_ID, faab=FAAB)
    mock_service.replace_player_claim.assert_called_once_with(
        add_id=ADD_ID, drop_id=DROP_ID, start=NEXT_MIDNIGHT, faab=FAAB
    )


def test_drop_player(controller, mock_service, mock_get_start_fixed):
    controller.drop_player(DROP_ID, START_STR)
    mock_service.drop_player.assert_called_once_with(drop_id=DROP_ID, start=START_DT)


def test_drop_player_no_start(controller, mock_service, mock_get_start_midnight):
    controller.drop_player(DROP_ID)
    mock_service.drop_player.assert_called_once_with(
        drop_id=DROP_ID, start=NEXT_MIDNIGHT
    )
