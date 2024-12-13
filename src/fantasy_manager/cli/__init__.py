"""fantasy-manager

Usage:
    fantasy-manager <command> [<args>...]
    fantasy-manager --help

The most commonly used fantasy-manager commands are:

roster   Change roster composition (e.g. add or drop players)
lineup   Change lineup (e.g. sit/start decisions)

For more details, see 'fantasy-manager <command> --help'
"""

from pathlib import Path
import sys
import logging
import importlib
from fantasy_manager.cli.command import CliCommand, error_result, not_permitted_result
from fantasy_manager.exceptions import FantasyManagerError, FantasyManagerSoftError
import docopt

CLI_DIRECTORY = Path(__file__).parent

ALL_COMMANDS = [
    command.stem
    for command in CLI_DIRECTORY.iterdir()
    if command.is_file() and command.name != "__init__.py"
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_help():
    commands_list = "\n".join(f"    {cmd}" for cmd in ALL_COMMANDS)
    return f"""fantasy-manager

Usage:
    fantasy-manager <command> [<args>...]
    fantasy-manager --help

The available commands are:

{commands_list}

For more details, see 'fantasy-manager <command> --help'
"""


def main():
    """Entry point for cli"""
    args = docopt.docopt(__doc__, options_first=True)
    command_name = args["<command>"]
    argv = [command_name] + args["<args>"]

    if command_name == "help":
        print(generate_help())
        return 0
    if command_name not in ALL_COMMANDS:
        print(f"Error: Command '{command_name}' not found.")
        return 1
    try:
        module = importlib.import_module(f"fantasy_manager.cli.{command_name}")
        command = next(
            klass
            for name, klass in vars(module).items()
            if isinstance(klass, type)
            and issubclass(klass, CliCommand)
            and klass is not CliCommand
        )()
    except ModuleNotFoundError:
        print(f"Error: Command '{command_name}' not found.")
        return 1
    except StopIteration:
        print(f"Error: No valid command class found in '{command_name}'.")
        return 1

    command_args = command.parse_args(argv)

    try:
        result = command.run(command_args)
    except FantasyManagerSoftError as err:
        result = not_permitted_result(str(err))
    except FantasyManagerError as err:
        result = error_result(str(err))
    except Exception as err:
        logger.exception(f"Unexpected error while executing {command_name}: {err}")
        result = error_result("An unexpected error occurred")

    # TODO: check out logger from rally.neptune
    logger.info(result.message)
    logger.info(
        f"Command '{command_name}' executed with return code {result.return_code}"
    )
    return result.return_code


if __name__ == "__main__":
    sys.exit(main())
