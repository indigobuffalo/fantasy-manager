from datetime import datetime
import logging
from pathlib import Path
from typing import Optional

from fantasy_manager.service.roster import RosterService
from fantasy_manager.util.cli import get_start
from fantasy_manager.util.log import join_with_padding, log_tuples
from fantasy_manager.util.log import log_line_break
from fantasy_manager.util.temporal import (
    get_time_until_start_str,
    seconds_to_hours_mins_and_secs,
    upcoming_midnight,
)

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class RosterController:
    def __init__(self, league_name: str):
        self.service = RosterService(league_name=league_name)

    def _get_player_info_strs(
        self, add_id: Optional[int] = None, drop_id: Optional[int] = None
    ) -> dict[str, str]:
        add_tuple = None
        drop_tuple = None

        if add_id is not None:
            add_player_data = self.service.get_player_data(add_id)
            add_tuple = (add_player_data.name, "[" + add_player_data.player_id + "]")
        if drop_id is not None:
            drop_player_data = self.service.get_player_data(drop_id)
            drop_tuple = (drop_player_data.name, "[" + drop_player_data.player_id + "]")

        players_with_ids = join_with_padding(
            tuples=[
                (add_player_data.name, f"[{add_player_data.player_id}]"),
                (drop_player_data.name, f"[{drop_player_data.player_id}]"),
            ],
            separator=" ",
        )
        pass

    def log_inputs(
        self,
        start: datetime,
        add_id: Optional[int] = None,
        drop_id: Optional[int] = None,
    ) -> None:

        add_player_data = self.service.get_player_data(add_id)
        if drop_id is not None:
            drop_player_data = self.service.get_player_data(drop_id)

        # TODO: handle add-only
        players_with_ids = join_with_padding(
            tuples=[
                (add_player_data.name, f"[{add_player_data.player_id}]"),
                (drop_player_data.name, f"[{drop_player_data.player_id}]"),
            ],
            separator=" ",
        )

        pairs = [
            ("League", self.service.league.name),
            ("Add", players_with_ids[0]),
            ("Drop", players_with_ids[1]),
            ("Start", get_time_until_start_str(start)),
        ]

        log_line_break(logger)
        log_tuples(logger=logger, tuples=pairs, padding=4)
        log_line_break(logger)

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
        self.log_inputs(start=start_dt, add_id=add_id)
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
        self.log_inputs(start=start_dt, add_id=add_id, drop_id=drop_id)
        self.service.replace_player(add_id=add_id, drop_id=drop_id, start=start_dt)
