"""Make a change to your roster via Free Agency"""
import copy
from datetime import datetime
from typing import Any

from fantasy_manager.cli import command
from fantasy_manager.controller.roster import RosterController
from fantasy_manager.util.misc import cli_arg_to_int, confirm_proceed
from fantasy_manager.util.time_utils import upcoming_midnight


def format_args(args: list[str]) -> dict[str, Any]:
    formatted = copy.deepcopy(args)
    formatted["--league"] = args["--league"]
    formatted["--add"] = (
        cli_arg_to_int("--add", args["--add"]) if args["--add"] is not None else None
    )
    formatted["--drop"] = (
        cli_arg_to_int("--drop", args["--drop"]) if args["--drop"] is not None else None
    )
    formatted["--now"] = args["--now"]
    if formatted["--now"]:
        formatted["--start"] = None
    else:
        formatted["--start"] = (
            datetime.fromisoformat(args["--start"])
            if args["--start"]
            else upcoming_midnight()
        )
    return formatted


def add_player(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, start, run_now = args["--add"], args["--start"], args["--now"]
    if run_now:
        confirm_proceed()
    controller.log_inputs(add_id=add_id)
    controller.add_player_with_delay(add_id=add_id, start=start, run_now=run_now)
    command.success_result(f"Succesfully added player {add_id}")


def drop_player(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    drop_id, start, run_now = args["--drop"], args["--start"], args["--now"]
    if run_now:
        confirm_proceed()
    controller.log_inputs(drop_id=drop_id)
    controller.drop_player_with_delay(drop_id=drop_id, start=start, run_now=run_now)
    command.success_result(f"Succesfully dropped player {drop_id}")


def replace_player(
    args: dict[str, Any], controller: RosterController
) -> command.success_result:
    add_id, drop_id, start, run_now = (
        args["--add"],
        args["--drop"],
        args["--start"],
        args["--now"],
    )
    if run_now:
        confirm_proceed()
    controller.log_inputs(add_id=add_id, drop_id=drop_id)
    controller.replace_player_with_delay(
        add_id=add_id, drop_id=drop_id, start=start, run_now=run_now
    )
    command.success_result(
        f"Succesfully added player {add_id} and dropped player {drop_id}"
    )


class Roster(command.CliCommand):
    """fantasy-manager roster
    Usage:
        fantasy-manager roster add --league=<league_name> --add=<player_id> [--start=<start_date> | -n | --now]
        fantasy-manager roster drop --league=<league_name> --drop=<player_id> [--start=<start_date> | -n | --now]
        fantasy-manager roster replace --league=<league_name> --add=<player_id>  --drop=<player_id> [--start=<start_date> | -n | --now]

    Options:
          --league=<league>     Id of the league the team is under.
          --add=<player_id>     Id of player to add.
          --drop=<player_id>    Id of player to drop.
          -n,--now              Execute script immediately [default: False]."""

    def run(self, args: dict) -> command.CommandResult:
        """Update roster by adding, dropping and/or submitting waiver claims for players"""

        args = format_args(args)
        controller = RosterController(league_name=args["--league"])

        match args:
            case args if args["add"] == True:
                return add_player(args, controller)
            case args if args["drop"] == True:
                return drop_player(args, controller)
            case args if args["replace"] == True:
                return replace_player(args, controller)
