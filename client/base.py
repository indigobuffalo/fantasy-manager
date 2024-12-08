from abc import ABC, abstractmethod

import requests
from requests import Response

from config.config import FantasyConfig
from model.league import League
from model.team import Team


class BaseClient(ABC):
    def __init__(self, league: League, config: FantasyConfig):
        self.config = config
        self.session = requests.Session()
        self.league = league

    @property
    @abstractmethod
    def team_url(self):
        """The url to the fantasy team page."""
        pass

    @abstractmethod
    def get_team(self) -> Team:
        """Fetch team response."""
        pass

    @abstractmethod
    def check_current_auth(self):
        """Ensure the current session is authenticated."""
        pass

    @abstractmethod
    def add_player(self, add_id: str, drop_id: str = None) -> Response:
        """Add a player to the roster.

        Args:
            add_id (str): The id of player to add.
            drop_id (str, optional): The id of player to drop. Defaults to None.

        Returns:
            Response: Response of the add player request.
        """
        pass

    @abstractmethod
    def place_waiver_claim(
        self, add_id: str, drop_id: str = None, faab: int = None
    ) -> Response:
        """Place a waiver caim.

        Args:
            add_id (str): The id of player to add.
            drop_id (str, optional): The id of player to drop. Defaults to None.
            faab (int, optional): The amount of faab to bid on the player. Defaults to None.

        Returns:
            Response: Response of the waiver claim request.
        """
        pass

    @abstractmethod
    def cancel_waiver_claim(self, player_id: str) -> Response:
        """Cancel a waiver claim.

        Args:
            player_id (str): The id of the player in the waiver claim.

        Returns:
            Response: Response of the cancel waiver request.
        """
        pass

    # TODO: convert this into a get_player_data method that returns model of all player data
    @abstractmethod
    def get_player_by_id(self, player_id: int) -> str:
        """Translate a player id into a player name.

        Args:
            player_id (int): The id of the player.

        Returns:
            str: The name of the player.
        """
