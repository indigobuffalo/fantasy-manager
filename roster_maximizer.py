import yaml
from pathlib import Path
from typing import Dict, List

class PositionExhaustedError(Exception):

   def __init__(self, position: str):
        super().__init__(f"No openings at position '{position}'")

class Player:

    def __init__(self, id: int, name: str, positions: List[str], rank: int):
        self.id = id
        self.name = name
        self.positions = positions
        self.rank = rank

class RosterDay:

    openings = {
        'C': 2,
        'LW': 3,
        'RW': 3,
        'D': 4,
        'UTIL': 1,
        'G': 2
    }

    potential_starts = {
        'C': 0,
        'LW': 0,
        'RW': 0,
        'D': 0,
        'G': 0
    }

    positional_scarcity = {
        'C': 0,
        'LW': 0,
        'RW': 0,
        'D': 0,
        'G': 0
    }

    def __init__(self, players_raw: Dict = {}):
        self.skaters = self.instantiate_players(players_raw['skaters'])
        self.goalies = self.instantiate_players(players_raw['goalies'])
        self.populate_potential_starts()
        self.calculate_positional_scarcity()

    @staticmethod
    def instantiate_players(players_raw: List[Dict]):
        players = []
        for player_rank, player_attrs in players_raw.items():
            positions = player_attrs['positions']
            if 'IR' in positions:
                continue

            name = player_attrs['name']
            id =  player_attrs['id']
            players.append(Player(id=id, name=name, positions=positions, rank=player_rank))
        return players

    @property
    def center_one(self)
        return self._center_one
    
    @center_one.setter
    def center_one(self, player: Player)
        self._center_one = player

    @property
    def center_two(self)
        return self._center_two
    
    @center_two.setter
    def center_two(self, player: Player)
        self._center_two = player

    @property
    def lw_one(self, player: Player)
        self._lw_one = player

    @lw_one.setter
    def lw_one(self, player: Player)
        self._lw_one = player

    @property
    def lw_two(self, player: Player)
        self._lw_two = player

    @lw_two.setter
    def lw_two(self, player: Player)
        self._lw_two = player

    @property
    def lw_three(self, player: Player)
        self._lw_three = player

    @lw_three.setter
    def lw_three(self, player: Player)
        self._lw_three = player

    @property
    def rw_one(self, player: Player)
        self._rw_one = player

    @rw_one.setter
    def rw_one(self, player: Player)
        self._rw_one = player
    
    @property
    def rw_two(self, player: Player)
        self._rw_two = player

    @rw_two.setter
    def rw_two(self, player: Player)
        self._rw_two = player
    
    @property
    def rw_three(self, player: Player)
        self._rw_three = player

    @rw_three.setter
    def rw_three(self, player: Player)
        self._rw_three = player
    
    @property
    def d_one(self, player: Player)
        self._d_one = player

    @d_one.setter
    def d_one(self, player: Player)
        self._d_one = player
    
    def set_positions(self):
        single_pos_players = [p for p in self.skaters if len(p['position'].split('/')) == 1]
        dual_pos_players = [p for p in self.skaters if len(p['position'].split('/')) == 2]
        tri_pos_players = [p for p in self.skaters if len(p['position'].split('/')) == 3]

    
    def set_position(self, position: str, player: Dict):
        positions = player['positions']
        
        openings_for_position = self.openings[position]

        if openings_for_position == 0:
            raise PositionExhaustedError(position)

    def populate_potential_starts(self):
        for player in self.skaters:
            for position in player.positions:
                self.potential_starts[position] += 1
        for player in self.goalies:
            for position in player.positions:
                self.potential_starts[position] += 1

    def calculate_positional_scarcity(self):
        """Positive value indicates surplus, negative value indicates shortage"""
        self.positional_scarcity['C'] = self.potential_starts['C'] - self.openings['C']
        self.positional_scarcity['RW'] = self.potential_starts['RW'] - self.openings['RW']
        self.positional_scarcity['LW'] = self.potential_starts['LW'] - self.openings['LW']
        self.positional_scarcity['D'] = self.potential_starts['D'] - self.openings['D']
        self.positional_scarcity['G'] = self.potential_starts['G'] - self.openings['G']

if __name__ == '__main__':
    project_dir = Path(__file__).parent
    rosters = Path(project_dir, 'data/rosters')
    roster = Path(rosters, '2020-02-28_complete.yml')
    with open(roster) as f:
        roster_data = yaml.safe_load(f)
    roster_day = RosterDay(roster_data)