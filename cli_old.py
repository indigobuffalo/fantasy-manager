#!/Users/Akerson/.local/share/virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python
"""Make a change to your roster.

Usage:
  update_roster.py waivers --league=<league_name> --add=<player_id> [--faab=<faab>] [--drop=<player_id>] [--start=<start_date> | -n | --now]
  update_roster.py lineup --league=<league_name> [--roster-file=<path_to_roster_file>] [--start=<start_date>] [--end=<end_date>]
  update_roster.py check --league=<league_name> --check=<players_to_check>

Options:
  --drop=<player_id>    Id of player to drop.
  -n,--now              Execute script immediately.

"""
from datetime import datetime, date, timedelta

from docopt import docopt

from config.config import FantasyConfig
from controller.roster import RosterController
from util.time_utils import date_range, days_until, upcoming_midnight
from exceptions import AlreadyAddedError, InvalidLeagueError, NotOnRosterError


def get_start_for_waiver_add(start: str, run_now: bool = False) -> bool:
    if run_now:
        return datetime.now()
    return datetime.fromisoformat(start) if start else upcoming_midnight()


def get_unrostered(players: set[str]) -> list:
    unrostered = list()
    for player in players:
        if not controller.is_rostered(player):
            unrostered.append(player)


def print_contextual_info(league: str) -> None:
    print(f"Transaction for league: '{league_name.upper()}'")


if __name__ == "__main__":
    args = docopt(__doc__)
    league_name = args["--league"]

    # controller = RosterController(league_name=league_name, season=season)
    controller = RosterController(league_name=league_name)
    controller.check_current_auth()

    print_contextual_info(league_name)

    if args["check"]:
        players = set(args["--check"].split(","))
        unrostered_players = get_unrostered(players)
        if len(unrostered_players) > 0:
            raise NotOnRosterError(f"Players not on roster: {unrostered_players}'!")
        else:
            print(f"Success! All players on roster - {players}")

    if args["lineup"]:
        start, end = args["--start"], args["--end"]

        if start is not None:
            start_date = datetime.strptime(start, "%Y-%m-%d")
        else:
            start_date = date.today() + timedelta(days=1)
        if end is not None:
            end_date = datetime.strptime(end, "%Y-%m-%d")
        else:
            days_until_sunday = days_until("Sunday", start_date)
            end_date = start_date + timedelta(days=days_until_sunday)

        roster_file = args["--roster-file"] if args["--roster-file"] else "default.yml"
        for game_date in date_range(start_date, end_date):
            resp = controller.edit_lineup(roster_file, game_date)
    elif args["waivers"]:
        add_player_id = args["--add"]
        start, run_now = args["--start"], args["--now"]
        faab = args["--faab"]
        add_datetime = get_start_for_waiver_add(start, run_now)
        try:
            controller.add_free_agent(
                add_id=add_player_id,
                add_datetime=add_datetime,
                drop_id=args["--drop"],
                faab=faab,
            )
        except AlreadyAddedError:
            print(f"Player '{add_player_id}' is on roster, all set!")
            pass
