from datetime import datetime, date
from pathlib import Path
from pdb import run
from typing import Optional

from service.roster import RosterService

PROJECT_DIR = Path(__file__).parent.absolute()


class RosterController:
    def __init__(self, league_name: str):
        self.service = RosterService(league_name=league_name)

    # TODO
    def on_waivers(self, player_id):
        pass

    # TODO
    def cancel_waiver_claim(self, player_id: str):
        pass

    def print_inputs(
        self,
        add_id: str,
        drop_id: Optional[str] = None,
        waiver: bool = False,
        faab: Optional[int] = 0,
    ) -> None:
        not_applicable = "-"
        labels_and_values = {
            "League": self.service.league.name,
            "Add": self.service.get_player_data(add_id).name.full,
            "Drop": self.service.get_player_data(drop_id).name.full
            if drop_id is not None
            else not_applicable,
            "Type": "Waiver Claim" if waiver else "Free Agent",
            "FAAB": faab if waiver else None,
        }

        def print_with_padding(
            lable_value_pairs: list[tuple[str, str]], padding_width: int
        ) -> None:
            print()
            for label, val in lable_value_pairs:
                print(f"{label}{':'.ljust(padding_width - len(label))}{val}")
            print()

        max_label_width = 0
        label_values_pairs = []
        for l, v in labels_and_values.items():
            if v:
                max_label_width = max(max_label_width, len(l))
                label_values_pairs.append((l, v))

        print_with_padding(label_values_pairs, max_label_width + 2)

    def get_league(self) -> str:
        return self.service.league.to_json()

    def get_player(self, player_id: int) -> str:
        """Gets player data and returns it as a json string

        Args:
            player_id (int): The id of the player to fetch data for.

        Returns:
            str: Json-serialized dict representing the player.
        """
        return self.service.get_player_data(player_id).to_json()

    def add_free_agent(self, add_id: str, drop_id: str) -> None:
        return self.service.add_free_agent(add_id=add_id, drop_id=drop_id)

    def add_player_with_delay(
        self,
        add_id: str,
        drop_id: str = None,
        start: datetime = None,
        waiver: bool = False,
        faab: int = None,
        run_now: bool = False,
    ):
        self.service.add_player_with_delay(
            add_id=add_id,
            drop_id=drop_id,
            start=start,
            waiver=waiver,
            faab=faab,
            run_now=run_now,
        )

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
