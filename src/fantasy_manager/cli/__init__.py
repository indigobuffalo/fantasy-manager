"""fantasy-manager

Usage:
    fantasy-manager <command> [<args>...]
    fantasy-manager --help

The available fantasy-manager commands are:

roster         Change roster composition (e.g. add or drop players)
lineup         Change lineup (e.g. sit/start decisions)
player         Look up players (e.g. availability across leagues)

For more details, see 'fantasy-manager <command> --help'
"""

from pathlib import Path
import sys
import logging
import importlib
from fantasy_manager.cli.command import CliCommand, error_result, not_permitted_result
from fantasy_manager.exceptions import FantasyManagerError, FantasyManagerSoftError
import docopt

from fantasy_manager.util.log import log_line_break
from fantasy_manager.util.output import OutputFormat, resolve_output_format, serialize

CLI_DIRECTORY = Path(__file__).parent

# Dedicated stdout logger (plain ``%(message)s``); structured ``--output``
# payloads go here so they stay clean for ``jq``/``yq``, while the CLI framing
# and diagnostics below use the stderr ``logger``.
stdout = logging.getLogger("stdout")

# A command is either a single module (e.g. roster.py) or a package whose
# __init__.py defines the command (e.g. player/, a namespace with sub-actions).
ALL_COMMANDS = [
    entry.stem
    for entry in CLI_DIRECTORY.iterdir()
    if entry.name != "__init__.py"
    and (
        (entry.is_file() and entry.suffix == ".py")
        or (entry.is_dir() and (entry / "__init__.py").exists())
    )
]

logger = logging.getLogger(__name__)


def main():
    """Entry point for cli"""
    args = docopt.docopt(__doc__, options_first=True)
    command_name = args["<command>"]
    argv = [command_name] + args["<args>"]

    if command_name not in ALL_COMMANDS:
        logger.info(f"Error: Command '{command_name}' not found.")
        return 1
    try:
        module = importlib.import_module(f"fantasy_manager.cli.{command_name}")
        command = next(
            klass
            for name, klass in vars(module).items()
            if isinstance(klass, type)
            and issubclass(klass, CliCommand)
            and klass is not CliCommand
            # Pick the command class *defined* in this module, not one it merely
            # imports — e.g. the `player` package imports its sub-action classes.
            and klass.__module__ == module.__name__
        )()
    except ModuleNotFoundError as err:
        logger.info(f"Error: Command '{command_name}' not found.")
        return 1
    except StopIteration:
        logger.info(f"Error: No valid command class found in '{command_name}'.")
        return 1

    try:
        command_args = command.parse_args(argv)
    except docopt.DocoptExit as err:
        logger.info(
            f"Error: invalid or missing arguments for '{command_name}'.\n{err.usage}"
        )
        return 1

    # Resolved once here (top level) so the serializer choice is independent of
    # which command — or namespaced sub-action — parses the remaining arguments.
    output_format = OutputFormat.TEXT
    try:
        output_format = resolve_output_format(argv)
        result = command.run(command_args)
    except FantasyManagerSoftError as err:
        result = not_permitted_result(exception=err, message=str(err))
    except FantasyManagerError as err:
        result = error_result(exception=err, message=str(err))
        logger.debug(result.traceback)
    except Exception as err:
        result = error_result(exception=err, message="An unexpected error occurred")
        logger.debug(result.traceback)

    # Machine-readable payload to stdout; the framing/summary below stays on
    # stderr so the two streams don't mix.
    if output_format.is_structured and result.data is not None:
        stdout.info(serialize(result.data, output_format))

    log_line_break(logger=logger, spacer="=", lines=2)
    logger.info(result.message)
    logger.info(
        f"Command '{command_name}' executed with return code {result.return_code}"
    )
    log_line_break(logger=logger, spacer="=", lines=2)
    return result.return_code


if __name__ == "__main__":
    sys.exit(main())
