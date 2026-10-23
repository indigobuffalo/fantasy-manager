"""Abstract base class for CLI commands
Allows for some centralization of common logic"""

from __future__ import annotations

from abc import ABC, abstractmethod
import traceback
from typing import Any, NamedTuple, Optional

import docopt

from fantasy_manager.util.output import OutputFormat


class CommandResult(NamedTuple):
    """Results of a Command run.

    ``data`` is an optional machine-readable payload (a plain dict/list) that the
    top-level runner serializes when ``--output json|yaml`` is requested. It's
    independent of ``message`` (the human-readable, stderr summary) and may be
    present on both success and error results, so structured consumers still get
    the partial payload when something goes wrong.

    ``output_format`` is the format the command parsed from its own ``--output``
    option. Carrying it on the result (rather than re-deriving it at the top
    level) keeps a single source of truth: the command's docopt parse is the
    only place ``--output`` is interpreted, so the runner can't disagree with
    the command about which format was requested.
    """

    return_code: int
    message: str
    traceback: Optional[str] = None
    data: Optional[Any] = None
    output_format: OutputFormat = OutputFormat.TEXT


def success_result(
    message: str,
    data: Optional[Any] = None,
    output_format: OutputFormat = OutputFormat.TEXT,
) -> CommandResult:
    """Returns a successful (return code 0) Command Result"""
    return CommandResult(
        return_code=0, message=message, data=data, output_format=output_format
    )


def error_result(
    exception: Exception,
    message: str,
    data: Optional[Any] = None,
    output_format: OutputFormat = OutputFormat.TEXT,
) -> CommandResult:
    """Returns a failed (return code 1) Command Result due to a 'hard' error"""
    return CommandResult(
        return_code=1,
        message=message,
        traceback=traceback.format_exc(),
        data=data,
        output_format=output_format,
    )


def not_permitted_result(
    exception: Exception,
    message: str,
    data: Optional[Any] = None,
    output_format: OutputFormat = OutputFormat.TEXT,
) -> CommandResult:
    """Returns a faield (return code 2) Command Result due to a business-logic driven error"""
    return CommandResult(
        return_code=2,
        message=message,
        traceback=traceback.format_exc(),
        data=data,
        output_format=output_format,
    )


def run_subcommand(action: "CliCommand", argv: list[str], label: str) -> CommandResult:
    """Parse ``argv`` against a sub-action's usage and run it.

    Namespace commands (e.g. ``player``) dispatch to a sub-action by re-parsing the
    remaining argv against that action's own usage. ``docopt.DocoptExit`` is a
    ``SystemExit``, so the top-level runner (which only catches ``Exception``) would
    let it escape — centralize the catch here so every namespace surfaces a clean
    per-action usage message instead. ``label`` names the action in that message
    (e.g. ``"player availability"``).
    """
    try:
        action_args = action.parse_args(argv)
    except docopt.DocoptExit as err:
        return error_result(
            err,
            f"Error: invalid or missing arguments for '{label}'.\n{err.usage}",
        )
    return action.run(action_args)


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
