#!/Users/Akerson/.virtualenvs/yahoo-fantasy-1EuG-xYP/bin/python

"""Add player to your team.

Usage:
  add_player.py --add=<player_id> [--league=<league> --drop=<player_id>]

Options:
  --drop=player_id    Id of player to drop.

"""

import os
import json
import requests
from docopt import docopt
from headers import COOKIE

TEAM_URL = 'https://hockey.fantasysports.yahoo.com/hockey/28012/1'
LOCKED_PLAYER = 'Huberdeau'
PLAYERS_FILE = 'players.json'


def check_current_auth(response):
    if (LOCKED_PLAYER not in response.text):
        raise RuntimeError('Not logged in!')
    

def check_already_added(response, p_add):
    if p_add in response.text:
        raise ValueError('Already added player!')


def add_player(league_id, headers, data):
    response = requests.post(f'https://hockey.fantasysports.yahoo.com/hockey/{league_id}/1/addplayer', headers=headers, data=data)
    if "You have reached the weekly" in response.text:
        raise ValueError("You have already reached max adds for the week!")
    if "player has already played and is no longer" in response.text:
        raise ValueError("Player to drop has played today - try tomorrow!")


def read_players_from_json():
    current_dir = os.path.dirname(os.path.realpath(__file__))
    with open(players_file, 'r') as p_file:
        players = json.loads(p_file.read())
    return players


def main(league_id, p_add, p_drop):
    headers = { 'cookie': COOKIE }
    data = {
      'stage': '3',
      'crumb': 'ItqN9ormBu.',
      'stat1': 'S',
      'stat2': 'D',
      'apid': p_add,
    }
    if p_drop:
        data['dpid'] = p_drop
    team_response = requests.get(TEAM_URL, headers=headers)
    check_current_auth(team_response)
    check_already_added(team_response, p_add)
    add_player(league_id, headers, data)


if __name__ == '__main__':
    args = docopt(__doc__)
    add_id = args['--add']
    drop_id = args['--drop']
    league_id = args['--league'] or '28012'
    main(league_id, add_id, drop_id)

