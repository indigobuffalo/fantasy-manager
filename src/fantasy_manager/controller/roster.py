from datetime import datetime
import logging
from pathlib import Path
from typing import Optional

from fantasy_manager.service.roster import RosterService
from fantasy_manager.util.misc import log_line_break, confirm_proceed
from fantasy_manager.util.time_utils import upcoming_midnight

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class RosterController:
    def __init__(self, league_name: str):
        self.service = RosterService(league_name=league_name)

    def log_inputs(
        self,
        add_id: Optional[int] = None,
        drop_id: Optional[int] = None,
    ) -> None:
        not_applicable = "-"
        labels_and_values = {
            "League": self.service.league.name,
            "Add": self.service.get_player_data(add_id).name.full
            if add_id is not None
            else not_applicable,
            "Drop": self.service.get_player_data(drop_id).name.full
            if drop_id is not None
            else not_applicable,
        }

        def log_all_with_padding(
            lable_value_pairs: list[tuple[str, str]], padding_width: int
        ) -> None:
            for label, val in lable_value_pairs:
                logger.info(f"{label}{':'.ljust(padding_width - len(label))}{val}")

        max_label_width = 0
        label_values_pairs = []
        for l, v in labels_and_values.items():
            if v:
                max_label_width = max(max_label_width, len(l))
                label_values_pairs.append((l, v))

        space_btwn_label_and_val = 2
        log_line_break(logger)
        log_all_with_padding(
            label_values_pairs, max_label_width + space_btwn_label_and_val
        )
        log_line_break(logger)

    def get_player(self, player_id: int) -> str:
        """Gets player data and returns it as a json string

        Args:
            player_id (int): The id of the player to fetch data for.

        Returns:
            str: Json-serialized dict representing the player.
        """
        return self.service.get_player_data(player_id).to_json()

    @staticmethod
    def _get_start(start: str) -> datetime:
        start = start.lower() if start is not None else None
        match start:
            case None:
                return upcoming_midnight()
            case "now":
                return datetime.now()
            case _:
                return datetime.fromisoformat(start)

    def add_player(
        self,
        add_id: int,
        start: Optional[str] = None,
    ) -> None:
        start_dt = self._get_start(start)
        self.log_inputs(add_id=add_id)
        if start_dt <= datetime.now():
            confirm_proceed()
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
        start_dt = self._get_start(start)
        self.log_inputs(add_id=add_id, drop_id=drop_id)
        if start_dt <= datetime.now():
            confirm_proceed()
        self.service.replace_player(add_id=add_id, drop_id=drop_id, start=start_dt)
