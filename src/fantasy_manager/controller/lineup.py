from datetime import date, datetime
import logging
from math import log
from pathlib import Path
import time

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.service.lineup import LineupService
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

    def set_lineup(self):
        pass

    def automate_lineup(self, start: str, end: str):
        start = datetime.strptime(start, "%Y-%m-%d").date()
        end = datetime.strptime(end, "%Y-%m-%d").date() if end else start
        self.log_inputs(start, end)
        self.service.automate_lineup(start, end)
