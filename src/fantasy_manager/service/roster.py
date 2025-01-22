import logging

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pytz import timezone

from fantasy_manager.client.base import BaseClient
from fantasy_manager.client.factory import ClientFactory
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import (
    AlreadyAddedError,
    FantasyUnknownError,
    InputError,
    NotOnRosterError,
    OnAnotherTeamError,
    TimeoutExceededError,
)
from fantasy_manager.model.league import League
from fantasy_manager.model.player import NhlPlayer
from fantasy_manager.model.team import Team
from fantasy_manager.util.log import align_pairs, log_pairs
from fantasy_manager.util.temporal import (
    duration_to_hours_mins_and_secs,
    get_timeout_end,
    now_pacific,
    sleep_until,
    sleep_verbose,
)

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)


class RosterService:
    def __init__(
        self, config: FantasyConfig, league: League, team: Team, client: BaseClient
    ):
        self.cfg = config
        self.league = league
        self.team = team

        self.client = client
        self.client.refresh()

    def _check_player_inputs(
        self,
        add_player: Optional[NhlPlayer] = None,
        drop_player: Optional[NhlPlayer] = None,
    ) -> None:
        if add_player is not None and self.team.has_player(add_player):
            raise AlreadyAddedError(add_player)
        if drop_player is not None and not self.team.has_player(drop_player):
            raise NotOnRosterError(drop_player)

    def get_player_data(self, player_id: int) -> NhlPlayer:
        return self.client.get_player_by_id(player_id)

    def run_preflight_checks(
        self, player_to_add: NhlPlayer, player_to_drop: Optional[NhlPlayer] = None
    ):
        """Run any checks that need to execute before main execution.

        Args:
            add (ApiPlayer): The player to add.
            drop (Optional[ApiPlayer]): The player to drop.
        """
        self.client.refresh()
        self._check_player_inputs(add_player=player_to_add, drop_player=player_to_drop)

    def prepare_to_execute(
        self,
        start: datetime,
        add_player: Optional[NhlPlayer] = None,
        drop_player: Optional[NhlPlayer] = None,
    ) -> None:
        """Prepares to execute the desired action.  Takes care of things like ensuring the
        client session is authenticated and player inputs are valid.

        Args:
            start (datetime): The time to perform the action.
            add_player (Optional[ApiPlayer], optional): The player to add. Defaults to None.
            drop_player (Optional[ApiPlayer], optional): The player to drop. Defaults to None.
        """
        preflight_check_dt = start - timedelta(seconds=self.cfg.PRE_FLIGHT_CHECK_SECS)
        sleep_until(preflight_check_dt, logger)
        self.run_preflight_checks(add_player, drop_player)
        sleep_until(start, logger)

    @staticmethod
    def _get_aligned_player_names(
        add_player: Optional[NhlPlayer] = None, drop_player: Optional[NhlPlayer] = None
    ) -> tuple[Optional[str], Optional[str]]:
        match add_player, drop_player:
            case (NhlPlayer(), NhlPlayer()):
                player_names = align_pairs(
                    tuples=[
                        (add_player.name.full, f"[{add_player.player_id}]"),
                        (drop_player.name.full, f"[{drop_player.player_id}]"),
                    ],
                    separator=" ",
                )
                return player_names[0], player_names[1]
            case (NhlPlayer(), None):
                return [str(add_player), None]
            case (None, NhlPlayer()):
                return [None, str(drop_player)]
            case _:
                raise InputError(
                    f"Invalid player inputs: '{add_player}' and '{drop_player}'"
                )

    def refresh_team(self):
        self.team = self.client.get_team()

    def log_inputs(
        self,
        start: datetime,
        add_player: Optional[NhlPlayer] = None,
        drop_player: Optional[NhlPlayer] = None,
        faab: Optional[int] = None,
    ):
        """Logs inputs to enable verification by user.

        Args:
            start (datetime): The time to exeucte the action.
            add_player (Optional[ApiPlayer]): The player to add. Defaults to None.
            drop_player (Optional[ApiPlayer]): The player to drop. Defaults to None.
            faab (Optional[int]): The amount of faab to bid if this is a waiver claim.
        """
        hrs, mins, secs = duration_to_hours_mins_and_secs(start - now_pacific())
        add_str, drop_str = self._get_aligned_player_names(add_player, drop_player)
        pairs = [
            ("League", self.league.name),
            ("Start", f"{int(hrs)} HOURS {int(mins)} MINUTES {int(secs)} SECONDS"),
            ("Add", add_str),
            ("Drop", drop_str),
        ]
        if faab is not None:
            pairs.append(("FAAB", f"${faab}"))
        log_pairs(logger=logger, tuples=pairs, padding=4)

    def add_player(self, add_id: str, start: datetime) -> None:
        """Adds a player from free agency to the roster.

        Args:
            add_id (int): The id of the player to add
            start (datetime): The datetime to execute the transaction

        Raises:
            FantasyUnknownError: _description_
        """
        add_player = self.get_player_data(add_id)
        self.log_inputs(start, add_player=add_player)
        self.prepare_to_execute(add_player=add_player, start=start)

        end = get_timeout_end(start, self.cfg.TIMEOUT_SECONDS)

        while True:
            now = now_pacific()
            logger.info(f"The time is {now}.")
            if now > end:
                raise TimeoutExceededError(
                    f"Failed to add '{add_player}' within {self.cfg.TIMEOUT_SECONDS} second timeout"
                )
            try:
                self.client.add_player(add_id=add_id)
                self.refresh_team()
                if not self.team.has_player(add_player):
                    raise FantasyUnknownError(f"Error adding '{add_player}'.")
                logger.info(f"Success!  {add_player} is now on roster.")
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

    def add_player_claim(self, add_id: str, faab: int, start: datetime) -> None:
        """Make a waiver claim for a player.

        Args:
            add_id (int): The id of the player to add
            faab (int): The amount of faab to bid on the player.
            start (datetime): The datetime to execute the transaction

        Raises:
            FantasyUnknownError: _description_
        """
        add_player = self.get_player_data(add_id)
        self.log_inputs(start, add_player=add_player, faab=faab)
        self.prepare_to_execute(add_player=add_player, start=start)
        return self.client.add_player_claim(add_id=add_id, faab=faab)

    def replace_player(self, add_id: int, drop_id: int, start: datetime) -> None:
        """Replaces a rostered player with one from free agency.

        Args:
            add_id (int): The id of the player to add
            drop_id (int, optional): The id of the player to drop. Defaults to None.
            start (datetime): The datetime to execute the transaction.

        Raises:
            FantasyUnknownError: _description_
        """
        add_player = self.get_player_data(add_id)
        drop_player = self.get_player_data(drop_id)
        self.log_inputs(start, add_player, drop_player)

        self.prepare_to_execute(
            add_player=add_player, drop_player=drop_player, start=start
        )

        end = get_timeout_end(start, self.cfg.TIMEOUT_SECONDS)
        while True:
            now = now_pacific()
            logger.info(f"The time is {now}")
            if now > end:
                raise TimeoutExceededError(
                    f"Failed to add '{add_player}' for '{drop_player}' within {self.cfg.TIMEOUT_SECONDS} second timeout"
                )
            try:
                self.client.replace_player(add_id=add_id, drop_id=drop_id)
                self.refresh_team()
                if not self.team.has_player(add_player):
                    raise FantasyUnknownError(
                        f"Error adding {add_player} for {drop_player}."
                    )
                logger.info(f"Success!  {add_player} is now on roster.")
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

    def replace_player_claim(
        self, add_id: str, drop_id: int, faab: int, start: datetime
    ) -> None:
        """Make a waiver claim to add one player and drop another.

        Args:
            add_id (int): The id of the player to add.
            drop_id(int): The id of the player to drop.
            faab (int): The amount of faab to bid on the player.
            start (datetime): The datetime to execute the transaction

        Raises:
            FantasyUnknownError: _description_
        """
        add_player = self.get_player_data(add_id)
        drop_player = self.get_player_data(drop_id)
        self.log_inputs(
            start, add_player=add_player, drop_player=drop_player, faab=faab
        )
        self.prepare_to_execute(
            add_player=add_player, drop_player=drop_player, start=start
        )
        return self.client.replace_player_claim(
            add_id=add_id, drop_id=drop_id, faab=faab
        )

    def drop_player(self, drop_id: str, start: datetime) -> None:
        """Drops a player from the roster.

        Args:
            drop_id (str, optional): The id of the player to drop. Defaults to None.

        Raises:
            FantasyUnknownError: Raises an error if something goes awry.
        """
        drop_player = self.get_player_data(drop_id)
        self.log_inputs(start, drop_player=drop_player)
        self.prepare_to_execute(drop_player=drop_player, start=start)

        self.client.drop_player(drop_player.player_id)

        self.refresh_team()
        if self.team.has_player(drop_player):
            raise FantasyUnknownError(f"Error dropping '{drop_player}'.")
