from datetime import datetime
from unittest.mock import Mock
import zoneinfo

import pytest
from freezegun import freeze_time

from fantasy_manager.service.roster import RosterService
from fantasy_manager.controller.roster import RosterController
from fantasy_manager.exceptions import InputError


@pytest.fixture
def controller():
    mock_svc = Mock(spec=RosterService)
    yield RosterController(mock_svc)


@pytest.fixture
def add_id():
    return 123


@pytest.fixture
def drop_id():
    return 456


@pytest.fixture
def start_str():
    return "2025-01-28T23:59:30-08:00"


@pytest.fixture
def start_dt(start_str):
    return datetime.fromisoformat(start_str)


@pytest.fixture
def invalid_start():
    return "fh3qaf"


@pytest.fixture
def faab():
    return 99


FZN_ONE_AM_PAC = datetime(
    2025, 1, 2, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Pacific")
)
FZN_ONE_AM_EST = datetime(
    2025, 1, 2, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Eastern")
)


def test_add_player(controller, add_id, start_str, start_dt):
    controller.add_player(add_id, start_str)
    controller.service.add_player.assert_called_once_with(add_id=add_id, start=start_dt)


@pytest.mark.parametrize(
    "freeze_time_dt, expected_midnight_pacific",
    [
        (
            FZN_ONE_AM_PAC,
            datetime(2025, 1, 3, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
        (
            FZN_ONE_AM_EST,
            datetime(2025, 1, 2, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
    ],
)
def test_add_player_no_start(
    controller, freeze_time_dt, expected_midnight_pacific, add_id
):
    with freeze_time(freeze_time_dt):
        controller.add_player(add_id)
        controller.service.add_player.assert_called_once_with(
            add_id=add_id, start=expected_midnight_pacific
        )


def test_add_player_invalid_start(controller, add_id, invalid_start):
    with pytest.raises(InputError):
        controller.add_player(add_id, invalid_start)


def test_replace_player(controller, add_id, drop_id, start_str, start_dt):
    controller.replace_player(add_id=add_id, drop_id=drop_id, start=start_str)
    controller.service.replace_player.assert_called_once_with(
        add_id=add_id, drop_id=drop_id, start=start_dt
    )


@pytest.mark.parametrize(
    "freeze_time_dt, expected_midnight_pacific",
    [
        (
            FZN_ONE_AM_PAC,
            datetime(2025, 1, 3, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
        (
            FZN_ONE_AM_EST,
            datetime(2025, 1, 2, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
    ],
)
def test_replace_player_no_start(
    controller, freeze_time_dt, expected_midnight_pacific, add_id, drop_id
):
    with freeze_time(freeze_time_dt):
        controller.replace_player(add_id=add_id, drop_id=drop_id)
        controller.service.replace_player.assert_called_once_with(
            add_id=add_id, drop_id=drop_id, start=expected_midnight_pacific
        )


def test_replace_player_invalid_start(controller, add_id, drop_id, invalid_start):
    with pytest.raises(InputError):
        controller.replace_player(add_id=add_id, drop_id=drop_id, start=invalid_start)


def test_add_player_claim(controller, add_id, start_str, start_dt, faab):
    controller.add_player_claim(add_id=add_id, faab=faab, start=start_str)
    controller.service.add_player_claim.assert_called_once_with(
        add_id=add_id, faab=faab, start=start_dt
    )


@pytest.mark.parametrize(
    "freeze_time_dt, expected_midnight_pacific",
    [
        (
            FZN_ONE_AM_PAC,
            datetime(2025, 1, 3, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
        (
            FZN_ONE_AM_EST,
            datetime(2025, 1, 2, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
    ],
)
def test_add_player_claim_no_start(
    controller, freeze_time_dt, expected_midnight_pacific, add_id, faab
):
    with freeze_time(freeze_time_dt):
        controller.add_player_claim(add_id, faab=faab)
        controller.service.add_player_claim.assert_called_once_with(
            add_id=add_id, faab=faab, start=expected_midnight_pacific
        )


def test_add_player_claim_invalid_start(controller, add_id, faab, invalid_start):
    with pytest.raises(InputError):
        controller.add_player_claim(add_id=add_id, faab=faab, start=invalid_start)


def test_replace_player_claim(controller, add_id, drop_id, start_str, start_dt, faab):
    controller.replace_player_claim(
        add_id=add_id, drop_id=drop_id, faab=faab, start=start_str
    )
    controller.service.replace_player_claim.assert_called_once_with(
        add_id=add_id, drop_id=drop_id, faab=faab, start=start_dt
    )


@pytest.mark.parametrize(
    "freeze_time_dt, expected_midnight_pacific",
    [
        (
            FZN_ONE_AM_PAC,
            datetime(2025, 1, 3, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
        (
            FZN_ONE_AM_EST,
            datetime(2025, 1, 2, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
    ],
)
def test_replace_player_claim_no_start(
    controller, freeze_time_dt, expected_midnight_pacific, add_id, drop_id, faab
):
    with freeze_time(freeze_time_dt):
        controller.replace_player_claim(add_id=add_id, drop_id=drop_id, faab=faab)
        controller.service.replace_player_claim.assert_called_once_with(
            add_id=add_id, drop_id=drop_id, start=expected_midnight_pacific, faab=faab
        )


def test_replace_player_invalid_start(controller, add_id, drop_id, faab, invalid_start):
    with pytest.raises(InputError):
        controller.replace_player_claim(
            add_id=add_id, drop_id=drop_id, start=invalid_start, faab=faab
        )


def test_drop_player(controller, drop_id, start_str, start_dt):
    controller.drop_player(drop_id, start_str)
    controller.service.drop_player.assert_called_once_with(
        drop_id=drop_id, start=start_dt
    )


@pytest.mark.parametrize(
    "freeze_time_dt, expected_midnight_pacific",
    [
        (
            FZN_ONE_AM_PAC,
            datetime(2025, 1, 3, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
        (
            FZN_ONE_AM_EST,
            datetime(2025, 1, 2, 0, 0, 0, tzinfo=zoneinfo.ZoneInfo("US/Pacific")),
        ),
    ],
)
def test_drop_player_no_start(
    controller, freeze_time_dt, expected_midnight_pacific, drop_id
):
    with freeze_time(freeze_time_dt):
        controller.drop_player(drop_id)
        controller.service.drop_player.assert_called_once_with(
            drop_id=drop_id, start=expected_midnight_pacific
        )


def test_drop_player_invalid_start(controller, drop_id, invalid_start):
    with pytest.raises(InputError):
        controller.drop_player(drop_id, invalid_start)
