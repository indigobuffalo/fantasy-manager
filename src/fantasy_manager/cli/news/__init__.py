"""The ``news`` command group: reads from external news/data sources.

This is a *namespace* command — it does no work itself, it dispatches to a
sub-action (``lineups`` today; e.g. ``injuries`` or ``starters`` later). The
top-level CLI hands us ``news <action> [<args>...]``; we look ``<action>`` up in
``ACTIONS`` and delegate, re-parsing the remaining argv against the sub-action's
own usage. It mirrors the ``player`` namespace exactly.

To add a new source command, drop a ``CliCommand`` subclass in a sibling module
and register it in ``ACTIONS`` below — nothing else needs to change.
"""
import logging
from typing import Any

import docopt

from fantasy_manager.cli import command
from fantasy_manager.cli.news.lineups import Lineups

logger = logging.getLogger(__name__)

# Registry of news sub-actions, keyed by the name typed on the command line.
ACTIONS: dict[str, type[command.CliCommand]] = {
    "lineups": Lineups,
}


class News(command.CliCommand):
    """fantasy-manager news

    Usage:
        fantasy-manager news <action> [<args>...]

    The available news actions are:

        lineups   Read NHL line combinations from DailyFaceoff

    For more details, see 'fantasy-manager news <action> --help'.
    """

    def parse_args(self, args: list[str]) -> dict[str, Any]:
        # ``options_first`` keeps flags intended for the sub-action (e.g.
        # ``--output``) in ``<args>`` instead of trying to parse them here.
        return docopt.docopt(self.__doc__, args, options_first=True)

    def run(self, args: dict[str, Any]) -> command.CommandResult:
        action_name = args["<action>"]
        action_cls = ACTIONS.get(action_name)
        if action_cls is None:
            known = ", ".join(sorted(ACTIONS))
            return command.error_result(
                ValueError(f"unknown news action: {action_name}"),
                f"Error: unknown news action '{action_name}'. Available actions: {known}.",
            )

        action = action_cls()
        action_argv = ["news", action_name] + args["<args>"]
        # ``run_subcommand`` parses the remaining argv against the sub-action's
        # usage and runs it, turning a docopt usage failure into a clean error
        # (shared so every namespace command handles it the same way).
        return command.run_subcommand(action, action_argv, f"news {action_name}")
