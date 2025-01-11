"""Miscellaneous utility functions"""

from datetime import datetime
from fantasy_manager.exceptions import InputError, UserAbortError


def prompt_run_now(exec_start: datetime) -> None:
    """Require user to confirm the desired action when the
    passed start time is now or in the past.

    Helps to avoid accidental irreversible actions.

    Args:
        exec_start (datetime): The time to execute the action.
    """
    if exec_start <= datetime.now():
        confirm_proceed()


def confirm_proceed() -> None:
    """Prompt for user input before performing task"""
    answer = input("Continue? [ y | n ]\n")
    if answer.upper() in ["Y", "YES"]:
        pass
    else:
        raise UserAbortError


def cli_arg_to_int(arg_name: str, arg_value: str) -> int:
    """Converts a CLI arg from a string to an int

    Args:
        arg_name (str): Name of the input arg
        arg_value (str): Value of the input arg

    Raises:
        FantasyManagerValueError: Custom error stating the arg name and value.
    """
    try:
        return int(arg_value)
    except ValueError as err:
        raise InputError(f"Expected int for '{arg_name}', got '{arg_value}'")
