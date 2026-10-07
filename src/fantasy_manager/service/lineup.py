import copy
from datetime import date, datetime, timedelta
import logging

from pathlib import Path
import re
from typing import Optional

from fantasy_manager.client.base import BaseFantasyClient
from fantasy_manager.client.nhl import NhlClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import InputError
from fantasy_manager.model.enums.position import Position
from fantasy_manager.model.game import Game
from fantasy_manager.model.league import League
from fantasy_manager.model.lineup import Lineup
from fantasy_manager.model.player import (
    AgnosticPlayer,
    LineupPlayer,
    RankedLineupPlayer,
)
from fantasy_manager.model.team import Team
from fantasy_manager.util.cli import confirm_proceed
from fantasy_manager.util.log import log_pairs
from fantasy_manager.util.temporal import now_pacific, sleep_until

PROJECT_DIR = Path(__file__).parent.absolute()


logger = logging.getLogger(__name__)

# Lineup slots that aren't real playing positions; a player can always be moved
# to one of these regardless of their position eligibility, and they don't count
# against the league's per-position starter limits.
BENCH_SLOTS = frozenset({Position.BN, Position.IR, Position.IR_PLUS})


class LineupService:
    def __init__(
        self,
        league: League,
        fantasy_client: BaseFantasyClient,
        nhl_client: NhlClient,
        config: FantasyConfig,
    ):
        self.config = config
        self.league = league
        self.nhl_client = nhl_client

        self.fantasy_client = fantasy_client
        self.fantasy_client.refresh()

        self.timeout_seconds = self.config.ADD_PLAYER_TIMEOUT_SECONDS

        self.agnostic_player_cache = {}

    def _get_agnostic_player(self, player_id: int) -> AgnosticPlayer:
        """Get the player from the fantasy client.

        Args:
            player_id (int): The id of the player to get.

        Returns:
            AgnosticPlayer: The player object.
        """
        if player_id not in self.agnostic_player_cache:
            player = self.fantasy_client.get_player_by_id(player_id)
            self.agnostic_player_cache[player_id] = player
        return self.agnostic_player_cache[player_id]

    def _plays_in_games(self, player: LineupPlayer, games: list[Game]) -> bool:
        """Check if the player plays in any of the given games.

        Args:
            player (LineupPlayer): The player to check.
            games (list[Game]): The list of games to check against.

        Returns:
            bool: True if the player plays in any of the games, False otherwise.
        """
        nhl_team = self.fantasy_client.get_player_by_id(player.player_id).team.abbr
        for game in games:
            if nhl_team in (game.home_team.abbr, game.away_team.abbr):
                return True
        return False

    def _get_players_playing_on_date(
        self, fantasy_team: Team, game_date: date
    ) -> list[LineupPlayer]:
        """Get the players that are playing on a given date.

        Args:
            fantasy_team (Team): The fantasy team to check.
            game_date (date): The date to check.

        Returns:
            list[LineupPlayer]: The list of players that are playing on the given date.
        """
        games_on_date = self.nhl_client.get_games_by_date(game_date)
        return [
            player
            for player in fantasy_team.roster
            if self._plays_in_games(player, games_on_date)
        ]

    def create_ranked_lineup_player(
        self,
        lineup_player: LineupPlayer,
        ranked_player: Optional[RankedLineupPlayer] = None,
    ) -> RankedLineupPlayer:
        """Create a RankedLineupPlayer instance from a LineupPlayer and RankedLineupPlayer.

        Args:
            lineup_player (LineupPlayer): The LineupPlayer instance.
            ranked_player (Optional[RankedLineupPlayer]): The RankedLineupPlayer instance. Defaults to None.

        Returns:
            RankedLineupPlayer: The created RankedLineupPlayer instance.
        """
        if ranked_player is None:
            logger.warning(
                f"Player {lineup_player.name.full} not found in rankings, using default rank."
            )
            return RankedLineupPlayer(
                rank=self.config.DEFAULT_PLAYER_RANK, **lineup_player.model_dump()
            )
        return RankedLineupPlayer(
            rank=ranked_player.rank,
            **lineup_player.model_dump(),
        )

    def _swap_selected_positions(
        player: RankedLineupPlayer,
        lineup: list[RankedLineupPlayer],
        open_slots: dict[str, int],
    ) -> list[RankedLineupPlayer]:
        """Swap the selected positions of a player with another player in the lineup."""
        pass

    def _fill_slot(
        self,
        player: RankedLineupPlayer,
        lineup: list[RankedLineupPlayer],
        open_slots: dict[str, int],
    ) -> Optional[RankedLineupPlayer]:
        """Fill a slot with a player.

        Args:
            player (RankedLineupPlayer): The player to fill the slot with.
            lineup (list[RankedLineupPlayer]): The current lineup.
            open_slots (dict[str, int]): The open slots to fill.

        Returns:
            Optional[RankedLineupPlayer]: The player that filled a slot with their selected position updated.
                                          None if no slot was filled.
        """
        potential_slots = {}
        for pos in player.eligible_positions:
            if open_slots[pos] > 0:
                potential_slots[pos] = open_slots[pos]

        if len(potential_slots) == 0:
            self._swap_selected_positions(player, lineup, open_slots)
            self._fill_slot(player, lineup, open_slots)
            return

        most_available_pos = max(potential_slots, key=potential_slots.get)
        player.selected_position = most_available_pos
        open_slots[most_available_pos] -= 1
        lineup.append(player)
        return RankedLineupPlayer

    def set_lineup(
        self,
        position_changes: list[dict],
        lineup_date: date,
        start: datetime,
    ) -> None:
        """Set specific players to specific lineup slots for a given date.

        The ``position_changes`` are a partial override: each entry names a
        ``player_id`` and the ``position`` to move them to. They are overlaid on
        the current roster (every other player keeps their existing slot) and the
        resulting full lineup is submitted to the fantasy client at ``start``.

        Args:
            position_changes (list[dict]): ``{"player_id": int, "position": str}``
                entries describing the slots to change.
            lineup_date (date): The date whose lineup is being set.
            start (datetime): When to submit the lineup (already resolved to a
                tz-aware Pacific datetime by the controller).
        """
        changes = self._parse_position_changes(position_changes)
        team = self.fantasy_client.get_team()
        players = self._overlay_changes(team, changes)
        self._validate_slot_counts(players)
        self._log_lineup_inputs(team, changes, lineup_date, start)
        sleep_until(start, logger, buffer_secs=self.config.FIRE_EARLY_BUFFER_SECS)
        self.fantasy_client.set_lineup(
            Lineup(day=lineup_date, players=players), lineup_date
        )
        logger.info(f"Success! Lineup set for {self.league.name} on {lineup_date}.")

    @staticmethod
    def _parse_position_changes(position_changes: list[dict]) -> dict[int, Position]:
        """Validate raw change entries into a ``player_id -> Position`` mapping."""
        if not position_changes:
            raise InputError("No lineup changes provided.")
        changes: dict[int, Position] = {}
        for entry in position_changes:
            try:
                player_id = int(entry["player_id"])
                position = Position(str(entry["position"]).upper())
            except (KeyError, TypeError):
                raise InputError(
                    f"Each lineup entry needs 'player_id' and 'position': {entry}"
                )
            except ValueError:
                raise InputError(
                    f"Invalid position '{entry.get('position')}' for player "
                    f"{entry.get('player_id')}. Valid: {[p.value for p in Position]}"
                )
            changes[player_id] = position
        return changes

    def _overlay_changes(
        self, team: Team, changes: dict[int, Position]
    ) -> list[LineupPlayer]:
        """Overlay the requested slot changes onto the current roster.

        Returns the full roster as ``LineupPlayer`` objects with the changed
        players' ``selected_position`` updated; unlisted players are unchanged.
        """
        roster_ids = {player.player_id for player in team.roster}
        unknown = set(changes) - roster_ids
        if unknown:
            raise InputError(f"Players not on the roster: {sorted(unknown)}")

        players: list[LineupPlayer] = []
        for player in team.roster:
            new_position = changes.get(player.player_id)
            if new_position is None:
                players.append(player)
                continue
            if (
                new_position not in BENCH_SLOTS
                and new_position not in player.eligible_positions
            ):
                eligible = [p.value for p in player.eligible_positions]
                raise InputError(
                    f"{player.name.full} ({player.player_id}) is not eligible for "
                    f"'{new_position.value}'. Eligible: {eligible}"
                )
            players.append(
                player.model_copy(update={"selected_position": new_position})
            )
        return players

    def _validate_slot_counts(self, players: list[LineupPlayer]) -> None:
        """Reject a lineup that puts more starters in a slot than the league allows."""
        counts: dict[Position, int] = {}
        for player in players:
            if player.selected_position in BENCH_SLOTS:
                continue
            counts[player.selected_position] = (
                counts.get(player.selected_position, 0) + 1
            )
        for position, count in counts.items():
            allowed = self.league.roster_configuration.get(position, 0)
            if count > allowed:
                raise InputError(
                    f"Too many players in '{position.value}': {count} assigned but "
                    f"only {allowed} slot(s) available."
                )

    def _log_lineup_inputs(
        self,
        team: Team,
        changes: dict[int, Position],
        lineup_date: date,
        start: datetime,
    ) -> None:
        """Log the pending lineup change for user verification; confirm if immediate."""
        names = {player.player_id: player.name.full for player in team.roster}
        pairs = [
            ("League", self.league.name),
            ("Lineup date", str(lineup_date)),
            ("Execute at", str(start)),
        ]
        for player_id, position in changes.items():
            pairs.append((names.get(player_id, str(player_id)), position.value))
        log_pairs(logger=logger, pairs=pairs, padding=4)

        if start <= now_pacific():
            confirm_proceed()

    def set_lineup_for_date(self, date_str: date, lineup_players: list[LineupPlayer]):
        # TODO: handle injured players
        roster_full = False
        open_slots = copy.deepcopy(self.league.roster_configuration)
        lineup = []
        rankings = self.config.get_player_rankings(self.league.name_abbr)
        ranked_players_sorted = sorted(
            [
                RankedLineupPlayer(
                    rank=rankings.get(
                        player.player_id, self.config.DEFAULT_PLAYER_RANK
                    ),
                    **player.model_dump(),
                )
                for player in lineup_players
            ],
            key=lambda plyr: plyr.rank,
            reverse=True,
        )
        import ipdb

        while not roster_full:
            ipdb.set_trace()
            player = ranked_players_sorted.pop(0)
            player_with_updated_pos = self._fill_slot(player, lineup, open_slots)
        pass

    def automate_lineup(self, start: date, end: date):
        team = self.fantasy_client.get_team()
        dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
        for dt in dates:
            players_playing = self._get_players_playing_on_date(team, dt)
            self.set_lineup_for_date(dt, players_playing)
