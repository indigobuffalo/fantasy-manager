"""Abstract base class for CLI commands
Allows for some centralization of common logic"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import NamedTuple

import docopt


class CommandResult(NamedTuple):
    """Results of a Command run"""

    return_code: int
    message: str


def success_result(message: str) -> CommandResult:
    """Returns a successful (return code 0) Command Result"""
    return CommandResult(return_code=0, message=message)


def error_result(message: str) -> CommandResult:
    """Returns a failed (return code 1) Command Result due to a 'hard' error"""
    return CommandResult(return_code=1, message=message)


def not_permitted_result(message: str) -> CommandResult:
    """Returns a faield (return codd 2) Command Result due to a business-logic driven error"""
    return CommandResult(return_code=2, message=message)


class CliCommand(ABC):
    """Abstract base class for CLI commands
    Allows for some centralization of common logic"""

    @abstractmethod
    def run(self, args: dict) -> CommandResult:
        """Does the command"""

    def parse_args(self, args: dict) -> dict:
        """Runs docopt on the command"""
        return docopt.docopt(self.__doc__, args)

    def _get_command_name(self) -> str:
        """Returns the name of the command"""
        return type(self).__name__
