from hamcrest import assert_that, equal_to
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from fantasy_manager.exceptions import InputError, UserAbortError
from fantasy_manager.util.cli import confirm_proceed, cli_arg_to_int, get_start
from fantasy_manager.util.temporal import PACIFIC_TZ


def test_confirm_proceed_yes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    confirm_proceed()


def test_confirm_proceed_no(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(UserAbortError):
        confirm_proceed()


def test_cli_arg_to_int_valid():
    assert_that(cli_arg_to_int("add_id", "4212"), equal_to(4212))


def test_cli_arg_to_int_invalid():
    with pytest.raises(InputError, match="Expected int for 'add_id', got 'abc'"):
        cli_arg_to_int("add_id", "abc")


def test_get_start_default():
    with patch("fantasy_manager.util.cli.upcoming_midnight_pacific") as mock_midnight:
        expected_dt = datetime(2025, 1, 1)
        mock_midnight.return_value = expected_dt
        assert_that(get_start(), equal_to(expected_dt))


def test_get_start_now():
    with patch("fantasy_manager.util.cli.now_pacific") as mock_now:
        expected_dt = datetime(2025, 1, 1, 12, 0, 0)
        mock_now.return_value = expected_dt
        assert_that(get_start("now"), equal_to(expected_dt))


def test_get_start_naive_iso_is_localized_to_pacific():
    # A naive ISO string (no offset) is anchored to Pacific so it stays
    # comparable to now_pacific(); otherwise log_inputs would raise a
    # naive-vs-aware TypeError.
    expected_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=PACIFIC_TZ)
    assert_that(get_start("2025-01-01T12:00:00"), equal_to(expected_dt))


def test_get_start_iso_with_offset_is_preserved():
    # An explicit offset is respected, not overwritten with Pacific.
    expected_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert_that(get_start("2025-01-01T12:00:00+00:00"), equal_to(expected_dt))


def test_get_start_invalid_iso():
    with pytest.raises(InputError, match="Invalid start time: invalid-time"):
        get_start("invalid-time")
