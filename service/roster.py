from time import sleep

from datetime import datetime, date
from pathlib import Path

from client.factory import ClientFactory
from config.config import FantasyConfig
from exceptions import (
    AlreadyAddedError,
    FantasyUnknownError,
    UserAbortError,
    NotOnRosterError,
    UnintendedWaiverAddError,
)
from model.player import Player
from util.time_utils import sleep_until, upcoming_midnight

PROJECT_DIR = Path(__file__).parent.absolute()


class RosterService:
    def __init__(self, league_name: str):
        self.config = FantasyConfig
        self.league = self.config.get_league(league_name)
        self.client = ClientFactory.get_client(
            platform=self.league.platform, league=self.league, config=self.config
        )

    def are_rostered(self, player_ids: list[str]) -> list[str]:
        unrostered = list()
        for player_id in player_ids:
            if not self.is_rostered(player_id):
                unrostered.append(player_id)
        return unrostered

    def is_rostered(self, player_id: str) -> bool:
        return player_id in self.client.get_team().players

    # TODO: FIX THIS on_waivers method
    def on_waivers(self, player_id):
        add_response = self.session.get(f"{self.team_url}/addplayer?apid={player_id}")
        return "Claim Player From Waivers" in add_response.text

    def cancel_waiver_claim(self, player_id: str):
        cancel_response = self.client.cancel_waiver_claim(player_id)
        if cancel_response.status_code == 200:
            print("Successfully canceled waiver claim")
        else:
            import ipdb

            ipdb.set_trace()
        return

    @staticmethod
    def confirm_proceed():
        answer = input("Continue? [ y | n ]\n")
        if answer.upper() in ["Y", "YES"]:
            return
        else:
            raise UserAbortError

    def get_player_data(self, player_id: str) -> Player:

        return self.client.get_player(player_id)

    def add_player_with_delay(self, add_id: str, start: datetime, drop_id: str = None):
        sleep_until(start)
        self.add_free_agent(add_id=add_id, drop_id=drop_id)

    def __check_add_player_inputs(self, add_id: str, drop_id: str) -> None:
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
        self.__check_add_player_inputs(add_id=add_id, drop_id=drop_id)
        self.client.place_waiver_claim(add_id=add_id, drop_id=drop_id, faab=faab)

    def add_free_agent(self, add_id: str, drop_id: str = None) -> None:
        """Adds a player from free agency to the roster.

        Args:
            add_id (str): The id of the player to add
            drop_id (str, optional): The id of the player to drop. Defaults to None.

        Raises:
            FantasyUnknownError: _description_
        """
        self.__check_add_player_inputs(add_id=add_id, drop_id=drop_id)

        # TODO: determine how to only add a player once they clear waivers
        # if self.on_waivers(add_id):
        #     raise OnWaiversError(f"Player {add_id} is on waivers!")

        while True:
            print(f"The time is {datetime.now()}.")
            try:
                # TODO: break out waiver claims into separate method
                # add_response = self.client.add_player(add_id=add_id, drop_id=drop_id, faab=faab)
                self.client.add_player(add_id=add_id, drop_id=drop_id)
                if not self.is_rostered(add_id):
                    raise FantasyUnknownError(f"Error - player '{add_id}' not added.")
                print(f"Success!  Player {add_id} is now on roster.")
                return
            except UnintendedWaiverAddError:
                waiver_wait_min = 30
                print("Accidentally added player to waivers, canceling now.")
                self.cancel_waiver_claim(add_id)
                print(
                    f"Waiting {waiver_wait_min} minutes for waivers to clear "
                    f"before trying to add player {add_id} from FA again."
                )
                sleep(waiver_wait_min * 60)
                continue
            except FantasyUnknownError as err:
                print(f"Error:{err} \nSleeping 0.1 seconds.")
                sleep(0.1)
                continue

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