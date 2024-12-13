"""Make a change to your roster"""
from datetime import datetime

from fantasy_manager.cli import command
from fantasy_manager.controller.roster import RosterController
from fantasy_manager.util.misc import confirm_proceed
from fantasy_manager.util.time_utils import upcoming_midnight


class Roster(command.CliCommand):
    """Usage:
    fantasy-manager roster --league=<league_name> --add=<player_id> [-w | --waivers] [--faab=<faab>] [--drop=<player_id>] [--start=<start_date> | -n | --now]

    Options:
      --league=<league>     Id of the league the team is under.
      --add=<player_id>     Id of player to add.
      --drop=<player_id>    Id of player to drop.
      --faab=<faab>         Amount of faab to spend [default: 0].
      -n,--now              Execute script immediately [default: False].
      -w,--waiver           Place waiver claim for player [default: False].
    """

    def run(self, args: dict) -> command.CommandResult:
        """Update roster by adding, dropping and/or submitting waiver claims for players"""
        league_name = args["--league"]

        controller = RosterController(league_name=league_name)

        add_id = int(args["--add"])
        drop_id = int(args["--drop"]) if args["--drop"] is not None else None
        start = args["--start"]
        run_now = args["--now"]
        faab = args["--faab"]
        waiver = args["--waiver"]

        controller.print_inputs(
            add_id=add_id, drop_id=drop_id, waiver=waiver, faab=faab
        )
        if run_now:
            confirm_proceed()
        else:
            start = datetime.fromisoformat(start) if start else upcoming_midnight()

        controller.add_player_with_delay(
            add_id=add_id,
            drop_id=drop_id,
            start=start,
            waiver=waiver,
            faab=faab,
            run_now=run_now,
        )
        return command.success_result("Yay we did it!")
