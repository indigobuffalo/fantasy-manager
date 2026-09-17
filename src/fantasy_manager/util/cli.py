"""Miscellaneous utility functions"""

from datetime import datetime
from typing import Optional
from fantasy_manager.exceptions import InputError, UserAbortError
from fantasy_manager.util.temporal import now_pacific, upcoming_midnight_pacific


def confirm_proceed() -> None:
    """Prompt for user input before performing task"""
    answer = input("\nContinue? [ y | n ]\n")
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
    except ValueError:
        raise InputError(f"Expected int for '{arg_name}', got '{arg_value}'")


def get_start(start: Optional[str] = None) -> datetime:
    """Get the datetime of execution based off of the "start" cli arg.

    Args:
        start (Optional[str]): Cli arg representing the desired execution time. Defaults to None.

    Returns:
        datetime: _description_
    """
    start = start.lower() if start is not None else None
    match start:
        case None:
            start_dt = upcoming_midnight_pacific()
        case "now":
            start_dt = now_pacific()
        case _:
            try:
                start_dt = datetime.fromisoformat(start)
            except ValueError:
                raise InputError(f"Invalid start time: {start}")
    return start_dt
