
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
from docopt import docopt

from controller.waivers import RosterController


def add_player(args) -> None:
    add_id, drop_id = args['--add'], args['--drop']
    start, run_now = args['--start'], args['--now']
    faab = args['--faab']

    if controller.is_rostered(add_id):
        print(f"Player '{add_id}' is on roster, all set!")
        return

    if run_now:
        return controller.add_player(add_id=add_id, drop_id=drop_id, faab=faab)
    
    return controller.add_player_with_delay(add_id=add_id, drop_id=drop_id, start=start, faab=faab)


def print_roster_check_results(results: list[str]) -> None:
    if len(results) > 0:
        print(f"Players not on roster: {results}")
    print("All players rostered")


if __name__ == '__main__':
    args = docopt(__doc__)
    league_name = args['--league']

    # controller = RosterController(league_name=league_name, season=season)
    controller = RosterController(league_name=league_name)
    controller.check_current_auth()

    if args['check']:
        player_ids = set(args['--check'].split(','))
        unrostered = controller.are_rostered(player_ids)
        print_roster_check_results(unrostered)
    elif args['lineup']:
        start, end = args['--start'], args['--end']
        roster_file = args['--roster-file']
        # resp = controller.edit_lineup(start, end roster_file, game_date)
    elif args['waivers']:
        add_player(args)
