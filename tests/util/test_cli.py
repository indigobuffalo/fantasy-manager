import pytest
from datetime import datetime
from unittest.mock import patch
from fantasy_manager.exceptions import InputError, UserAbortError
from fantasy_manager.util.cli import confirm_proceed, cli_arg_to_int, get_start


def test_confirm_proceed_yes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    confirm_proceed()


def test_confirm_proceed_no(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(UserAbortError):
        confirm_proceed()


def test_cli_arg_to_int_valid():
    assert cli_arg_to_int("test_arg", "42") == 42


def test_cli_arg_to_int_invalid():
    with pytest.raises(InputError, match="Expected int for 'test_arg', got 'abc'"):
        cli_arg_to_int("test_arg", "abc")


def test_get_start_default():
    with patch("fantasy_manager.util.cli.upcoming_midnight_pacific") as mock_midnight:
        mock_midnight.return_value = datetime(2025, 1, 1)
        assert get_start() == datetime(2025, 1, 1)


def test_get_start_now():
    with patch("fantasy_manager.util.cli.now_pacific") as mock_now:
        mock_now.return_value = datetime(2025, 1, 1, 12, 0, 0)
        assert get_start("now") == datetime(2025, 1, 1, 12, 0, 0)


def test_get_start_valid_iso():
    assert get_start("2025-01-01T12:00:00") == datetime(2025, 1, 1, 12, 0, 0)


def test_get_start_invalid_iso():
    with pytest.raises(InputError, match="Invalid start time: invalid-time"):
        get_start("invalid-time")
