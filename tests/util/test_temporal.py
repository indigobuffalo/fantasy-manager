from datetime import datetime, timedelta
import logging
from unittest.mock import Mock, patch
import zoneinfo

from freezegun import freeze_time
import pytest
from hamcrest import assert_that, equal_to

import fantasy_manager
from fantasy_manager.util.temporal import (
    duration_to_hours_mins_and_secs,
    get_timeout_end,
    now_pacific,
    sleep_until,
    sleep_verbose,
    upcoming_midnight_pacific,
)


FZN_ONE_AM_PAC = datetime(
    2025, 1, 2, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Pacific")
)
FZN_ONE_AM_EST = datetime(
    2025, 1, 2, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Eastern")
)


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def mock_now_pacific(monkeypatch):
    mock_now = datetime(2025, 2, 11, 12, 0, 0)
    monkeypatch.setattr(fantasy_manager.util.temporal, "now_pacific", lambda: mock_now)
    return mock_now


@pytest.fixture
def mock_sleep(monkeypatch):
    mock_sleep = Mock()
    monkeypatch.setattr(fantasy_manager.util.temporal, "sleep", mock_sleep)
    return mock_sleep


@pytest.mark.parametrize(
    "duration, hrs, mins, secs",
    [
        (timedelta(seconds=30), 0, 0, 30),
        (timedelta(hours=2, minutes=30, seconds=30), 2, 30, 30),
        (timedelta(days=1, hours=2, minutes=30, seconds=30), 26, 30, 30),
    ],
)
def test_duration_to_hours_mins_and_secs(duration, hrs, mins, secs):
    actual_hrs, actual_min, actual_secs = duration_to_hours_mins_and_secs(duration)
    assert_that(actual_hrs, equal_to(hrs))
    assert_that(actual_min, equal_to(mins))
    assert_that(actual_secs, equal_to(secs))


@patch(
    "fantasy_manager.util.temporal.duration_to_hours_mins_and_secs",
    return_value=(0, 5, 30),
)
def test_sleep_until_future(
    mock_duration_to, mock_sleep, mock_now_pacific, mock_logger
):
    sleep_duration = timedelta(minutes=5, seconds=30)
    target_dt = mock_now_pacific + sleep_duration
    buffer_secs = 3

    sleep_until(target_dt, mock_logger, buffer_secs)

    mock_logger.info.assert_called_once_with(
        f"Time until {target_dt.strftime('%Y-%m-%dT%H:%M:%S')}: '{sleep_duration}'. Sleeping 0 hours 5 minutes 30 seconds."
    )
    mock_sleep.assert_called_once_with(
        (target_dt - mock_now_pacific).total_seconds() - buffer_secs
    )


def test_sleep_until_past_time(mock_sleep, mock_now_pacific, mock_logger):
    target_dt = mock_now_pacific - timedelta(minutes=1)

    sleep_until(target_dt, mock_logger)

    mock_logger.info.assert_not_called()
    mock_sleep.assert_not_called()


def test_sleep_verbose(mock_sleep, mock_logger):
    sleep_secs = 10
    sleep_verbose(sleep_secs, mock_logger)

    mock_logger.info.assert_called_once_with(f"Sleeping for {sleep_secs} seconds...")
    mock_sleep.assert_called_once_with(sleep_secs)


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
def test_upcoming_midnight_pacific(freeze_time_dt, expected_midnight_pacific):
    with freeze_time(freeze_time_dt):
        actual = upcoming_midnight_pacific()
        assert_that(actual, equal_to(expected_midnight_pacific))


@pytest.mark.parametrize(
    "freeze_time_dt, expected_time_pacific",
    [
        (FZN_ONE_AM_PAC, FZN_ONE_AM_PAC),
        (
            FZN_ONE_AM_EST,
            datetime(2025, 1, 1, 22, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="US/Pacific")),
        ),
    ],
)
def test_now_pacific(freeze_time_dt, expected_time_pacific):
    with freeze_time(freeze_time_dt):
        actual = now_pacific()
        assert_that(actual, equal_to(expected_time_pacific))


def test_get_timeout_end_now():
    timeout_secs = 15
    expected = FZN_ONE_AM_PAC + timedelta(seconds=timeout_secs)

    with freeze_time(FZN_ONE_AM_PAC):
        actual = get_timeout_end(FZN_ONE_AM_PAC, timeout_secs)

    assert_that(actual, equal_to(expected))


def test_get_timeout_end_future():
    timeout_secs = 15
    future_start = FZN_ONE_AM_PAC + timedelta(weeks=1)
    expected = future_start + timedelta(seconds=timeout_secs)

    with freeze_time(FZN_ONE_AM_PAC):
        actual = get_timeout_end(future_start, timeout_secs)

    assert_that(actual, equal_to(expected))


def test_get_timeout_end_past():
    timeout_secs = 15
    past_start = FZN_ONE_AM_PAC + timedelta(weeks=-1)
    expected = FZN_ONE_AM_PAC + timedelta(seconds=timeout_secs)

    with freeze_time(FZN_ONE_AM_PAC):
        actual = get_timeout_end(past_start, timeout_secs)

    assert_that(actual, equal_to(expected))
