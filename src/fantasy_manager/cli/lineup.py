"""Make a change to your roster"""
from fantasy_manager.cli import command
from fantasy_manager.controller.roster import RosterController


class Lineup(command.CliCommand):
    """Usage:
    fantasy-manager roster --league=<league_name> --roster-file=<roster_file> [--start=<start_date> | -n | --now]

    Options:
      --league=<league>               Id of the league the team is under.
      --roster-file=<roster-file>     The name of the file holding the roster data.
      -n,--now                        Execute script immediately [default: False].
    """

    def run(self, args: dict) -> command.CommandResult:
        """Update roster by adding, dropping and/or submitting waiver claims for players"""
        league_name = args["--league"]

        controller = RosterController(league_name=league_name)

        start, end = args["--start"], args["--end"]
        roster_file = args["--roster-file"]
        # resp = controller.edit_lineup(start, end roster_file, game_date)
        return command.success_result("Yay we did it!")
