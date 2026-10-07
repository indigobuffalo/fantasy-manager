"""Make a change to your roster"""
import json
from pathlib import Path
from typing import Any

from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.exceptions import InputError
from fantasy_manager.service.lineup import LineupService
from fantasy_manager.cli import command
from fantasy_manager.controller.lineup import LineupController


def automate_lineup(
    args: dict[str, Any], controller: LineupController
) -> command.success_result:
    start, end = (args["--start"], args["--end"])
    controller.automate_lineup(start, end)
    return command.success_result(
        f"Succesfully set lineup for {controller.service.league.name}"
    )


def _load_position_changes(args: dict[str, Any]) -> list[dict]:
    """Read the lineup changes from either --lineup-file or --lineup-json."""
    lineup_file = args["--lineup-file"]
    lineup_json = args["--lineup-json"]
    if lineup_file:
        raw = Path(lineup_file).read_text()
    elif lineup_json:
        raw = lineup_json
    else:
        raise InputError("Must provide --lineup-file or --lineup-json.")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        raise InputError(f"Invalid lineup JSON: {err}")
    if not isinstance(data, list):
        raise InputError("Lineup JSON must be a list of {player_id, position} objects.")
    return data


def set_lineup(
    args: dict[str, Any], controller: LineupController
) -> command.success_result:
    position_changes = _load_position_changes(args)
    lineup_date = args["--date"]
    start = args["--start"]
    controller.set_lineup(
        position_changes=position_changes,
        lineup_date=lineup_date,
        start=start,
    )
    return command.success_result(
        f"Succesfully set lineup for {controller.service.league.name} on {lineup_date}"
    )


class Lineup(command.CliCommand):
    """Usage:
    fantasy-manager lineup automate --league=<league_name> --start=<start_date> [--end=<end_date>]
    fantasy-manager lineup set --league=<league_name> --date=<date> (--lineup-file=<lineup_file> | --lineup-json=<json>) [--start=<start_date>]

    Options:
      --league=<league>             Id of the league the team is under.
      --date=<date>                 The date (YYYY-MM-DD) whose lineup to set.
      --lineup-file=<lineup-file>   Path to a JSON file of {player_id, position} changes.
      --lineup-json=<json>          Inline JSON string of {player_id, position} changes.
      --start=<start_date>          When to execute. ISO 8601, or 'now'. For 'set' defaults to upcoming midnight Pacific; for 'automate' it is the first date to update.
      --end=<end_date>              The last date to update the lineup (automate only).
    """

    def run(self, args: dict) -> command.CommandResult:
        """Update lineup for the specified day(s)."""

        league_abbr = args["--league"]
        fc = FantasyConfig()
        league = fc.get_league(league_abbr)
        fantasy_client = ClientFactory.get_fantasy_client(
            platform=league.platform, league=league, config=fc
        )
        nhl_client = ClientFactory.get_nhl_client()
        service = LineupService(
            league=league,
            fantasy_client=fantasy_client,
            nhl_client=nhl_client,
            config=fc,
        )
        controller = LineupController(service=service)

        match args:
            case args if args["automate"] is True:
                return automate_lineup(args, controller)
            case args if args["set"] is True:
                return set_lineup(args, controller)

        return command.error_result(
            exception=InputError("No lineup subcommand matched."),
            message="No lineup subcommand matched.",
        )
