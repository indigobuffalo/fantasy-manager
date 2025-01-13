from datetime import datetime
import logging
from pathlib import Path
from typing import Optional

from fantasy_manager.service.roster import RosterService
from fantasy_manager.util.cli import get_start

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class RosterController:
    def __init__(self, league_name: str):
        self.service = RosterService(league_name=league_name)

    def get_player(self, player_id: int) -> str:
        """Gets player data and returns it as a json string

        Args:
            player_id (int): The id of the player to fetch data for.

        Returns:
            str: Json-serialized dict representing the player.
        """
        return self.service.get_player_data(player_id).to_json()

    def add_player(
        self,
        add_id: int,
        start: Optional[str] = None,
    ) -> None:
        start_dt = get_start(start)
        self.service.add_player(
            add_id=add_id,
            start=start_dt,
        )

    def drop_player(
        self,
        drop_id: int,
        start: Optional[str] = None,
    ) -> None:
        pass

    def replace_player(
        self, add_id: int, drop_id: int = None, start: Optional[str] = None
    ) -> None:
        start_dt = get_start(start)
        self.service.replace_player(add_id=add_id, drop_id=drop_id, start=start_dt)
