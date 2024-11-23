from time import sleep

from datetime import datetime, date
from pathlib import Path
from typing import Optional

from service.roster import RosterService
from util.time_utils import sleep_until, upcoming_midnight

PROJECT_DIR = Path(__file__).parent.absolute()


class RosterController:
    def __init__(self, league_name: str):
        self.service = RosterService(league_name=league_name)

    # TODO
    def on_waivers(self, player_id):
        pass

    # TODO
    def cancel_waiver_claim(self, player_id: str):
        pass

    def get_league(self) -> str:
        return self.service.league.to_json()

    def get_player(self, player_id: str) -> str:
        """Gets player data and returns it as a json string

        Args:
            player_id (str): The id of the player to fetch data for.

        Returns:
            str: Json-serialized dict representing the player.
        """
        return self.service.get_player_data(player_id).to_json()

    def add_free_agent(self, add_id: str, drop_id: str) -> None:
        return self.service.add_free_agent(add_id=add_id, drop_id=drop_id)

    def add_player_with_delay(
        self, add_id: str, drop_id: str = None, start: str = None, faab: int = None
    ):
        add_dt = datetime.fromisoformat(start) if start else upcoming_midnight()
        self.service.add_player_with_delay(add_id=add_id, drop_id=drop_id, start=add_dt)

    def place_waiver_claim(
        self, add_id: str, drop_id: Optional[str] = None, faab: Optional[int] = 0
    ) -> None:
        """Places a claim for a player on waivers.

        Args:
            add_id (str): _description_
            drop_id (str, optional): _description_. Defaults to None.
            faab (int, optional): _description_. Defaults to None.
        """
        self.__check_add_player_inputs(add_id=add_id, drop_id=drop_id)
        self.client.place_waiver_claim(add_id=add_id, drop_id=drop_id, faab=faab)

    def add_free_agent(self, add_id: str, drop_id: str = None) -> None:
        """Adds a player from free agency to the roster.

        Args:
            add_id (str): The id of the player to add
            drop_id (str, optional): The id of the player to drop. Defaults to None.

        Raises:
            FantasyUnknownError: _description_
        """
        # TODO: determine how to only add a player once they clear waivers
        # if self.on_waivers(add_id):
        #     raise OnWaiversError(f"Player {add_id} is on waivers!")

        self.service.add_free_agent(add_id=add_id, drop_id=drop_id)

    def edit_lineup(self, roster_filename: str, game_date: date):
        data = {
            "ret": "swap",
            "date": datetime.strftime(game_date, "%Y-%m-%d"),
            "stat1": "S",
            "stat2": "D",
            "crumb": self.config.get_crumb(self.league.platform),
        }
        roster_data = self.config.get_roster_data(self.league.name_abbr)
        data.update(roster_data)
        return self.session.post(f"{self.team_url}/editroster", data=data)
