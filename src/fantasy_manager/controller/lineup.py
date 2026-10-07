from datetime import date, datetime
import logging
from pathlib import Path
from typing import Optional

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.service.lineup import LineupService
from fantasy_manager.util.cli import get_start
from fantasy_manager.util.log import align_pairs, log_pairs

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class LineupController:
    def __init__(self, service: LineupService):
        self.service = service

    def log_inputs(self, start: date, end: date) -> None:
        pairs = [
            ("League", self.service.league.name),
            ("Start", str(start)),
            ("End", str(end)),
        ]
        log_pairs(logger=logger, pairs=pairs)

    def get_league(self) -> str:
        return self.service.league.to_json()

    def set_lineup(
        self,
        position_changes: list[dict],
        lineup_date: str,
        start: Optional[str] = None,
    ) -> None:
        """Set specific players to specific slots for a given date.

        Args:
            position_changes (list[dict]): ``{"player_id": int, "position": str}``
                entries describing the slots to change.
            lineup_date (str): The date (``YYYY-MM-DD``) whose lineup to set.
            start (Optional[str]): When to execute (ISO 8601 or ``now``). Defaults
                to upcoming midnight Pacific.
        """
        start_dt = get_start(start)
        lineup_dt = datetime.strptime(lineup_date, "%Y-%m-%d").date()
        self.service.set_lineup(
            position_changes=position_changes,
            lineup_date=lineup_dt,
            start=start_dt,
        )

    def automate_lineup(self, start: str, end: str):
        start = datetime.strptime(start, "%Y-%m-%d").date()
        end = datetime.strptime(end, "%Y-%m-%d").date() if end else start
        self.log_inputs(start, end)
        self.service.automate_lineup(start, end)
