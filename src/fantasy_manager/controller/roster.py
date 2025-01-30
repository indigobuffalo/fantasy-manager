import logging
from pathlib import Path
from typing import Optional

from fantasy_manager.service.roster import RosterService
from fantasy_manager.util.cli import get_start

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class RosterController:
    def __init__(self, service: RosterService):
        self.service = service

    def add_player(
        self,
        add_id: int,
        start: Optional[str] = None,
    ) -> None:
        """Add a player to the roster.

        Args:
            add_id (int): The id of the player to add.
            start (Optional[str], optional): The datetime to add the player. Defaults to midnght Pacific.
        """
        start_dt = get_start(start)
        self.service.add_player(
            add_id=add_id,
            start=start_dt,
        )

    def add_player_claim(
        self,
        add_id: int,
        faab: int = None,
        start: Optional[str] = None,
    ) -> None:
        """Make a claim for a player.

        Args:
            add_id (int): The id of the player to add.
            faab (int): The amount of faab to bid on the player.
            start (Optional[str], optional): The datetime to add the player. Defaults to midnght Pacific.
        """
        start_dt = get_start(start)
        self.service.add_player_claim(
            add_id=add_id,
            faab=faab,
            start=start_dt,
        )

    def drop_player(
        self,
        drop_id: int,
        start: Optional[str] = None,
    ) -> None:
        """Drops a player from the roster.

        Args:
            drop_id (int): The id of the player to drop.
            start (Optional[str], optional): The datetime to drop the player. Defaults to midnght Pacific.
        """
        start_dt = get_start(start)
        self.service.drop_player(drop_id=drop_id, start=start_dt)

    def replace_player(
        self, add_id: int, drop_id: int = None, start: Optional[str] = None
    ) -> None:
        start_dt = get_start(start)
        self.service.replace_player(add_id=add_id, drop_id=drop_id, start=start_dt)

    def replace_player_claim(
        self,
        add_id: int,
        drop_id: int,
        faab: int = None,
        start: Optional[str] = None,
    ) -> None:
        """Make a waiver claim to add one player and drop another.

        Args:
            add_id (int): The id of the player to add.
            drop_id(int): The id of the player to drop.
            faab (int): The amount of faab to bid on the player.
            start (Optional[str], optional): The datetime to add the player. Defaults to midnght Pacific.
        """
        start_dt = get_start(start)
        self.service.replace_player_claim(
            add_id=add_id,
            drop_id=drop_id,
            faab=faab,
            start=start_dt,
        )
