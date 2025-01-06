import logging
from time import sleep

from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    AlreadyAddedError,
    FantasyUnknownError,
    NotOnRosterError,
    OnAnotherTeamError,
    TimeoutExceededError,
)
from fantasy_manager.model.player import Player
from fantasy_manager.util.time_utils import sleep_until, sleep_verbose

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class LineupService:
    def __init__(self, league_name: str):
        self.config = FantasyConfig()
        self.league = self.config.get_league(league_name)
        self.client = ClientFactory.get_client(
            platform=self.league.platform, league=self.league, config=self.config
        )
        self.client.refresh()
        self.timeout_seconds = self.config.TIMEOUT_SECONDS

    def are_rostered(self, player_ids: list[str]) -> list[str]:
        unrostered = list()
        for player_id in player_ids:
            if not self.is_rostered(player_id):
                unrostered.append(player_id)
        return unrostered

    def is_rostered(self, player_id: int) -> bool:
        return player_id in [p.player_id for p in self.client.get_team().roster]

    # TODO: FIX THIS on_waivers method
    def on_waivers(self, player_id):
        add_response = self.session.get(f"{self.team_url}/addplayer?apid={player_id}")
        return "Claim Player From Waivers" in add_response.text

    def cancel_waiver_claim(self, player_id: str):
        cancel_response = self.client.cancel_waiver_claim(player_id)
        if cancel_response.status_code == 200:
            logger.info("Successfully canceled waiver claim")
        else:
            pass
        return

    def get_player_data(self, player_id: int) -> Player:
        return self.client.get_player_by_id(player_id)

    def run_preflight_checks(self, add_id: int, drop_id: Optional[int] = None):
        """Run any checks that need to execute before main execution.

        Args:
            add (int): Id of the player to add
            drop (Optional[int]): Id of the player to drop
        """
        self.client.refresh()
        self.__check_add_player_inputs(add_id=add_id, drop_id=drop_id)

    def prepare_to_add(
        self, start: datetime, add_id: int, drop_id: Optional[int] = None
    ) -> None:
        preflight_check_dt = start - timedelta(
            seconds=self.config.PRE_FLIGHT_CHECK_SECS
        )
        sleep_until(preflight_check_dt, logger)
        self.run_preflight_checks(add_id, drop_id)
        sleep_until(start, logger)

    def __check_add_player_inputs(self, add_id: int, drop_id: int) -> None:
        if self.is_rostered(add_id):
            raise AlreadyAddedError(add_id)
        if drop_id is not None and not self.is_rostered(drop_id):
            raise NotOnRosterError(drop_id)

    def place_waiver_claim(
        self, add_id: str, drop_id: str = None, faab: int = None
    ) -> None:
        """Places a claim for a player on waivers.

        Args:
            add_id (str): _description_
            drop_id (str, optional): _description_. Defaults to None.
            faab (int, optional): _description_. Defaults to None.
        """
        self.client.place_waiver_claim(add_id=add_id, drop_id=drop_id, faab=faab)

    def replace_player(self, add_id: int, drop_id: int, start: datetime) -> None:
        """Replaces a rostered player with one from free agency.

        Args:
            add_id (int): The id of the player to add
            drop_id (int, optional): The id of the player to drop. Defaults to None.
            start (datetime): The datetime to execute the transaction.

        Raises:
            FantasyUnknownError: _description_
        """
        self.prepare_to_add(add_id=add_id, drop_id=drop_id, start=start)

        end = start + timedelta(seconds=self.timeout_seconds)
        while True:
            logger.info(f"The time is {datetime.now()}")
            if datetime.now() > end:
                raise TimeoutExceededError(
                    f"Failed to replace player '{drop_id}' with player '{add_id}' within {self.timeout_seconds} second timeout"
                )
            try:
                self.client.replace_player(add_id=add_id, drop_id=drop_id)
                if not self.is_rostered(add_id):
                    raise FantasyUnknownError(f"Error - player '{add_id}' not added.")
                logger.info(f"Success!  Player {add_id} is now on roster.")
                return
            # TODO: use exception handling private method to reduce code duplication
            except Exception as err:
                match err:
                    case OnAnotherTeamError():
                        raise
                    case NotOnRosterError():
                        raise
                    case _:
                        logger.info(str(err))
                        sleep_verbose(0.1, logger)
                        continue

    def add_player(self, add_id: str, start: datetime) -> None:
        """Adds a player from free agency to the roster.

        Args:
            add_id (int): The id of the player to add
            start (datetime): The datetime to execute the transaction

        Raises:
            FantasyUnknownError: _description_
        """
        self.prepare_to_add(add_id=add_id, start=start)

        end = start + timedelta(seconds=self.timeout_seconds)
        while True:
            logger.info(f"The time is {datetime.now()}.")
            if datetime.now() > end:
                raise TimeoutExceededError(
                    f"Failed to add player '{add_id}' within {self.timeout_seconds} second timeout"
                )
            try:
                self.client.add_player(add_id=add_id)
                if not self.is_rostered(add_id):
                    raise FantasyUnknownError(f"Error - player '{add_id}' not added.")
                logger.info(f"Success!  Player {add_id} is now on roster.")
                return
            # TODO: use exception handling private method to reduce code duplication
            except Exception as err:
                match err:
                    case OnAnotherTeamError():
                        raise
                    case NotOnRosterError():
                        raise
                    case _:
                        logger.info(str(err))
                        sleep_verbose(0.1, logger)
                        continue

    def drop_player(self, drop_id: str, start: datetime) -> None:
        """Drops a player.

        Args:
            drop_id (str, optional): The id of the player to drop. Defaults to None.

        Raises:
            FantasyUnknownError: _description_
        """
        pass

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
