"""Miscellaneous utility functions"""

from fantasy_manager.exceptions import UserAbortError


def confirm_proceed() -> None:
    answer = input("Continue? [ y | n ]\n")
    if answer.upper() in ["Y", "YES"]:
        pass
    else:
        raise UserAbortError
