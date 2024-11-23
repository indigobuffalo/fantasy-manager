#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python
"""Make a change to your roster.

Usage:
  update_roster.py waivers --league=<league_name> --add=<player_id> [--faab=<faab>] [--drop=<player_id>] [--start=<start_date> | -n | --now]
  update_roster.py lineup --league=<league_name> [--roster-file=<path_to_roster_file>] [--start=<start_date>] [--end=<end_date>]
  update_roster.py check --league=<league_name> --check=<players_to_check>

Options:
  --drop=<player_id>    Id of player to drop.
  --faab=<faab>         Amount of faab to spend.
  -n,--now              Execute script immediately.

"""
import json
from operator import add
from typing import Optional
from docopt import docopt

from controller.roster import RosterController
from exceptions import UserAbortError


def confirm_proceed() -> None:
    answer = input("Continue? [ y | n ]\n")
    if answer.upper() in ["Y", "YES"]:
        pass
    else:
        raise UserAbortError


def print_add_player_inputs(
    league_data: str,
    add_player_data: str,
    drop_player_data: Optional[str] = None,
    faab: Optional[int] = None,
) -> None:
    label_width = 7
    print(f"{'League:'.ljust(label_width)} {json.loads(league_data)['name']}")
    print(f"{'Add:'.ljust(label_width)} {json.loads(add_player_data)['name']}")
    if drop_player_data:
        print(f"{'Drop:'.ljust(label_width)} {json.loads(drop_player_data)['name']}")
    if faab:
        print(f"{'FAAB:'.ljust(label_width)} {faab}")


def add_player(args) -> None:
    add_id, drop_id = args["--add"], args["--drop"]
    start, run_now = args["--start"], args["--now"]
    faab = args["--faab"]

    # TODO: call place_waiver_claim() for waiver claims

    league_data = controller.get_league()
    add_player_data = controller.get_player(add_id)
    drop_player_data = (
        controller.get_player(drop_id) if drop_id is not None else drop_id
    )
    print_add_player_inputs(
        league_data=league_data,
        add_player_data=add_player_data,
        drop_player_data=drop_player_data,
        faab=faab,
    )
    if run_now:
        confirm_proceed()
        return controller.add_free_agent(add_id=add_id, drop_id=drop_id)

    return controller.add_player_with_delay(
        add_id=add_id, drop_id=drop_id, start=start, faab=faab
    )


def print_roster_check_results(results: list[str]) -> None:
    if len(results) > 0:
        print(f"Players not on roster: {results}")
    print("All players rostered")


if __name__ == "__main__":
    args = docopt(__doc__)
    league_name = args["--league"]

    # controller = RosterController(league_name=league_name, season=season)
    controller = RosterController(league_name=league_name)
    controller.service.client.check_current_auth()

    if args["check"]:
        player_ids = set(args["--check"].split(","))
        unrostered = controller.are_rostered(player_ids)
        print_roster_check_results(unrostered)
    elif args["lineup"]:
        start, end = args["--start"], args["--end"]
        roster_file = args["--roster-file"]
        # resp = controller.edit_lineup(start, end roster_file, game_date)
    elif args["waivers"]:
        add_player(args)
