from datetime import date

from nhlpy import NHLClient

from fantasy_manager.model.game import Game
from fantasy_manager.transform.nhl import transform_nhl_raw_games_to_games


class NhlClient:
    def __init__(self, verbose: bool = False):
        self.client = NHLClient(verbose=verbose)

    def get_games_by_date(self, game_date: date) -> list[Game]:
        game_date_str = game_date.strftime("%Y-%m-%d")
        games_raw = self.client.schedule.get_schedule(game_date_str)["games"]
        transformed_games = [transform_nhl_raw_games_to_games(g) for g in games_raw]
        return [Game.model_validate(tfm) for tfm in transformed_games]
