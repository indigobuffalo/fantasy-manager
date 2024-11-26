#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python
"""Make a change to your roster.

Usage:
  cli.py roster --league=<league_name> --add=<player_id> [-w | --waivers] [--faab=<faab>] [--drop=<player_id>] [--start=<start_date> | -n | --now]
  cli.py lineup --league=<league_name> [--roster-file=<path_to_roster_file>] [--start=<start_date>] [--end=<end_date>]

Options:
  --drop=<player_id>    Id of player to drop.
  --faab=<faab>         Amount of faab to spend [default: 0].
  -n,--now              Execute script immediately [default: False].
  -w,--waiver           Place waiver claim for player [default: False].

"""
from docopt import docopt
from datetime import datetime

from controller.roster import RosterController
from exceptions import UserAbortError
from util.time_utils import upcoming_midnight


def confirm_proceed() -> None:
    answer = input("Continue? [ y | n ]\n")
    if answer.upper() in ["Y", "YES"]:
        pass
    else:
        raise UserAbortError


if __name__ == "__main__":
    args = docopt(__doc__)
    league_name = args["--league"]

    controller = RosterController(league_name=league_name)

    if args["lineup"]:
        start, end = args["--start"], args["--end"]
        roster_file = args["--roster-file"]
        # resp = controller.edit_lineup(start, end roster_file, game_date)
    elif args["roster"]:
        add_id, drop_id = args["--add"], args["--drop"]
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
            add_id=add_id, drop_id=drop_id, start=start, waiver=waiver, faab=faab
        )
