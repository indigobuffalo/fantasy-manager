#! /Users/Akerson/PythonVMs/practice/bin/python
"""Add player to your team.

Usage:
  add_player.py  --league=<league> --add=<player_id> [--drop=<player_id>]

Options:
  --drop=player_id    Id of player to drop.

"""

import requests
from docopt import docopt
from headers import COOKIE



def main(league_id, player_to_add, player_to_drop):
    headers = { 'cookie': COOKIE }

    team_response  = requests.get('https://hockey.fantasysports.yahoo.com/hockey/28012/1', headers=headers)
    if (f'"{player_to_drop}"' not in team_response.text) or (f'"{player_to_add}"' in team_response.text):
        print("Already added player")
        return

    data = {
      'stage': '3',
      'crumb': 'oBt5tsk3nQG',
      'stat1': 'S',
      'stat2': 'D',
      'apid': player_to_add,
      'dpid': player_to_drop 
    }
    add_response = requests.post(f'https://hockey.fantasysports.yahoo.com/hockey/{league_id}/1/addplayer', headers=headers, data=data)

    print(add_response)
    print("have reached" in add_response.text)

if __name__ == '__main__':
    args = docopt(__doc__)
    league_id = args['--league']
    add_id = args['--add']
    drop_id = args.get('--drop')
    main(league_id, add_id, drop_id)

