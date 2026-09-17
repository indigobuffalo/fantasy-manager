"""Make a change to your roster"""
from logging import config
from typing import Any
from fantasy_manager.cli.roster import format_args
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.client.factory import ClientFactory
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


def set_lineup(
    args: dict[str, Any], controller: LineupController
) -> command.success_result:
    lineup_file = args["--lineup-file"]
    start, end = (args["--start"], args["--end"])
    controller.automate_lineup()
    return command.success_result(
        f"Succesfully automated lineup for {controller.service.league.name}"
    )


class Lineup(command.CliCommand):
    """Usage:
    fantasy-manager lineup automate --league=<league_name> --start=<start_date> [--end=<end_date>]
    fantasy-manager lineup set --league=<league_name> --lineup-file=<lineup_file>

    Options:
      --league=<league>             Id of the league the team is under.
      --lineup-file=<lineup-file>   The name of the file holding the linuep data.
      --start=<start_date>          The first date to update the lineup.
      --end=<start_date>            The last date to update the linuep.
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

        lineup_file = args["--lineup-file"]
        return command.success_result("Yay we did it!")
