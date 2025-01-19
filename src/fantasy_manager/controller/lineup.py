import logging
from pathlib import Path

from fantasy_manager.service.lineup import LineupService

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class LineupController:
    def __init__(self, league_name: str):
        self.service = LineupService(league_name=league_name)

    def log_inputs(
        self,
    ) -> None:
        # TODO: log league, start, end
        pass

    def get_league(self) -> str:
        return self.service.league.to_json()

    def set_lineup(self):
        pass

    def automate_lineup(self):
        self.service.automate_lineup()
