from abc import ABC, abstractmethod

import requests
from requests import Response

from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.league import League
from fantasy_manager.model.team import Team


class BaseFantasyClient(ABC):
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
    def refresh(self):
        """Refresh client auth and handles."""
        pass

    @abstractmethod
    def add_player(self, add_id: int) -> None:
        """Add a player to the roster.

        Args:
            add_id (int): The id of player to add.
        """
        pass

    @abstractmethod
    def add_player_claim(self, add_id: int, faab: int = None) -> Response:
        """Make a waiver claim to add one player to the roster.

        Args:
            add_id (str): The id of player to add.
            faab (int, optional): The amount of faab to bid on the player. Defaults to None.

        Returns:
            Response: Response of the waiver claim request.
        """
        pass

    @abstractmethod
    def drop_player(self, drop_id: int) -> None:
        """Drops a player from the roster.

        Args:
            drop_id (int): The id of the player to drop.
        """
        pass

    @abstractmethod
    def replace_player(self, add_id: int) -> None:
        """Add one player to the roster while dropping another.

        Args:
            add_id (int): The id of player to add.
            drop_id (int, optional): The id of player to drop. Defaults to None.
        """
        pass

    @abstractmethod
    def replace_player_claim(
        self, add_id: int, drop_id: int, faab: int = None
    ) -> Response:
        """Make a waiver claim to add one player to the roster while dropping another.

        Args:
            add_id (str): The id of player to add.
            drop_id (str): The id of player to drop.
            faab (int, optional): The amount of faab to bid on the player. Defaults to None.

        Returns:
            Response: Response of the waiver claim request.
        """
        pass

    @abstractmethod
    def cancel_waiver_claim(self, player_id: int) -> Response:
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
