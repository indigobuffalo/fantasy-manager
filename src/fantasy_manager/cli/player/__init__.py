"""The ``player`` command group: lookups for individual players.

This is a *namespace* command — it doesn't do any work itself, it dispatches to
a sub-action (``availability``, and in future ``stats`` etc.). The top-level CLI
hands us ``player <action> [<args>...]``; we look ``<action>`` up in ``ACTIONS``
and delegate, re-parsing the remaining argv against the sub-action's own usage.

To add a new lookup, drop a ``CliCommand`` subclass in a sibling module and
register it in ``ACTIONS`` below — nothing else needs to change.
"""
import logging
from typing import Any

import docopt

from fantasy_manager.cli import command
from fantasy_manager.cli.player.availability import Availability

logger = logging.getLogger(__name__)

# Registry of player sub-actions, keyed by the name typed on the command line.
ACTIONS: dict[str, type[command.CliCommand]] = {
    "availability": Availability,
}


class Player(command.CliCommand):
    """fantasy-manager player

    Usage:
        fantasy-manager player <action> [<args>...]

    The available player actions are:

        availability   Check whether players are rostered or available across leagues

    For more details, see 'fantasy-manager player <action> --help'.
    """

    def parse_args(self, args: list[str]) -> dict[str, Any]:
        # ``options_first`` keeps flags intended for the sub-action (e.g.
        # ``--leagues``) in ``<args>`` instead of trying to parse them here.
        return docopt.docopt(self.__doc__, args, options_first=True)

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        action_name = args["<action>"]
        action_cls = ACTIONS.get(action_name)
        if action_cls is None:
            known = ", ".join(sorted(ACTIONS))
            return command.error_result(
                ValueError(f"unknown player action: {action_name}"),
                f"Error: unknown player action '{action_name}'. Available actions: {known}.",
            )

        action = action_cls()
        action_argv = ["player", action_name] + args["<args>"]
        # ``run_subcommand`` parses the remaining argv against the sub-action's
        # usage and runs it, turning a docopt usage failure into a clean error
        # (shared so every namespace command handles it the same way).
        return command.run_subcommand(
            action, action_argv, f"player {action_name}"
        )
