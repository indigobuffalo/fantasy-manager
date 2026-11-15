"""The ``league`` command group: league-wide, read-only reports.

Like ``player``, this is a *namespace* command — it does no work itself, it
dispatches to a sub-action (``moves``, and in future standings/matchup reports).
The top-level CLI hands us ``league <action> [<args>...]``; we look ``<action>``
up in ``ACTIONS`` and delegate, re-parsing the remaining argv against the
sub-action's own usage.

To add a new league report, drop a ``CliCommand`` subclass in a sibling module
and register it in ``ACTIONS`` below — nothing else needs to change.
"""

import logging
from typing import Any

import docopt

from fantasy_manager.cli import command
from fantasy_manager.cli.league.moves import Moves

logger = logging.getLogger(__name__)

# Registry of league sub-actions, keyed by the name typed on the command line.
ACTIONS: dict[str, type[command.CliCommand]] = {
    "moves": Moves,
}


class League(command.CliCommand):
    """fantasy-manager league

    Usage:
        fantasy-manager league <action> [<args>...]

    The available league actions are:

        moves   Show each manager's remaining weekly moves and FAAB

    For more details, see 'fantasy-manager league <action> --help'.
    """

    def parse_args(self, args: list[str]) -> dict[str, Any]:
        # ``options_first`` keeps flags intended for the sub-action (e.g.
        # ``--league``) in ``<args>`` instead of trying to parse them here.
        return docopt.docopt(self.__doc__, args, options_first=True)

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        action_name = args["<action>"]
        action_cls = ACTIONS.get(action_name)
        if action_cls is None:
            known = ", ".join(sorted(ACTIONS))
            return command.error_result(
                ValueError(f"unknown league action: {action_name}"),
                f"Error: unknown league action '{action_name}'. Available actions: {known}.",
            )

        action = action_cls()
        action_argv = ["league", action_name] + args["<args>"]
        # ``run_subcommand`` parses the remaining argv against the sub-action's
        # usage and runs it, turning a docopt usage failure into a clean error
        # (shared so every namespace command handles it the same way).
        return command.run_subcommand(action, action_argv, f"league {action_name}")
