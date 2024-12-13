"""Miscellaneous utility functions"""

from logging import Logger
from fantasy_manager.exceptions import (
    FantasyManagerError,
    FantasyManagerValueError,
    UserAbortError,
)


def confirm_proceed() -> None:
    """Prompt for user input before performing task"""
    answer = input("Continue? [ y | n ]\n")
    if answer.upper() in ["Y", "YES"]:
        pass
    else:
        raise UserAbortError


def log_line_break(
    logger: Logger, spacer: str = "-", count: int = 60, lines: int = 1
) -> None:
    """Log out line breaks for clarity in view log messages

    Args:
        logger (Logger): The logger to use.
        spacer (str, optional): The character to use to create the line break. Defaults to "=".
        countr (int, optional): The number of times to repeat the spacer. Defaults to 65=.
        lines (int, optional): THe number of consecutive line breaks to log. Defaults to 1.
    """
    for _ in range(lines):
        logger.info(spacer * count)
