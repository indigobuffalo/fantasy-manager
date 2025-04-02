import os
import json
from pathlib import Path
from typing import Any, Optional
import yaml

from dotenv import load_dotenv

from fantasy_manager.exceptions import InvalidLeagueError
from fantasy_manager.model.league import League
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.model.lineup import Lineup
from fantasy_manager.model.player import RankedPlayer


load_dotenv()
CONFIG_DIR = Path(__file__).parent.absolute()


class FantasyConfig:
    """Application configuration, including dynamic season-based paths."""

    VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    if LOG_LEVEL not in VALID_LOG_LEVELS:
        LOG_LEVEL = "INFO"

    PRE_FLIGHT_CHECK_SECS = 30

    PLATFORM_URLS = {
        Platform.ESPN: {
            PlatformUrl.FANTASY_HOCKEY: "http://todo.com",
            PlatformUrl.NHL: "http://todo.com",
        },
        Platform.FANTRAX: {
            PlatformUrl.FANTASY_HOCKEY: "http://todo.com",
            PlatformUrl.NHL: "http://todo.com",
        },
        Platform.YAHOO: {
            PlatformUrl.FANTASY_HOCKEY: "https://hockey.fantasysports.yahoo.com/hockey",
            PlatformUrl.NHL: "https://sports.yahoo.com/nhl",
        },
    }

    ADD_PLAYER_TIMEOUT_SECONDS = os.getenv("TIMEOUT_SECONDS", 15)
    ADD_PLAYER_POLL_SECONDS = os.getenv("POLL_SECONDS", 0.1)
    DEFAULT_PLAYER_RANK = os.getenv("DEFAULT_PLAYER_RANK", 70)  # used for streamers
    SEASON = os.getenv("FANTASY_SEASON", "2024_2025")
    YAHOO_CREDS_FILE = os.getenv("YAHOO_CREDS_FILE")
    YEAR = os.getenv("YEAR", "2024")

    @classmethod
    def get_platform_url(cls, platform: Platform, key: PlatformUrl) -> str:
        """Retrieve a specific URL for the platform and key."""
        platform_urls = cls.PLATFORM_URLS.get(platform, {})
        url = platform_urls.get(key)
        if not url:
            raise KeyError(
                f"No URL found for key '{key}' in platform '{platform.name}'."
            )
        return url

    @classmethod
    def get_league(cls, league_name: str) -> League:
        """Load league-specific configuration on demand, considering the current season."""
        league_file = (
            CONFIG_DIR / f"data/season/{cls.SEASON}/league/{league_name.lower()}.json"
        )

        if not league_file.exists():
            raise InvalidLeagueError(
                f"No configuration file found for league: {league_name} in season {cls.SEASON}"
            )

        with open(league_file) as f:
            json_data = json.load(f)
            return League.from_dict(json_data)

    @classmethod
    def get_lineup(cls, lineup_name: str) -> Lineup:
        """Load league-specific configuration on demand, considering the current season."""
        lineup_file = (
            CONFIG_DIR / f"data/season/{cls.SEASON}/lineup/{lineup_name.lower()}.json"
        )

        if not lineup_file.exists():
            raise InvalidLeagueError(
                f"No configuration file found for lineup: {lineup_name} in season {cls.SEASON}"
            )

        with open(lineup_file) as f:
            json_data = json.load(f)
            return Lineup.from_dict(json_data)

    @classmethod
    def get_player_rankings(
        cls, league_abbr: str, roster_name: Optional[str] = None
    ) -> list[RankedPlayer]:
        """Get player rankings for a specific league and roster.

        Args:
            league_abbr (str): Abbreviated name league name.
            roster_name (Optional[str], optional): Name of the roster (e.g. default, custom_123). Defaults to None.

        Raises:
            FileNotFoundError: _description_
            ValueError: _description_
            ValueError: _description_

        Returns:
            list[RankedPlayer]: _description_
        """
        suffix = f"_{roster_name}" if roster_name is not None else ""
        players = []
        roster_file = (
            CONFIG_DIR
            / f"data/season/{cls.SEASON}/roster/{league_abbr.lower()}{suffix}.json"
        )
        if not roster_file.exists():
            raise FileNotFoundError(f"Roster file not found: '{roster_file}'.")
        try:
            with open(roster_file, "r") as f:
                json_data = json.load(f)

            if not isinstance(json_data, list):
                raise ValueError(
                    f"Invalid data format in roster file: {roster_file}. Expected a dictionary."
                )
        except json.decoder.JSONDecodeError as e:
            raise ValueError(f"Error parsing JSON file '{roster_file}': {e}")

        for player_data in json_data:
            players.append(RankedPlayer.from_roster_file(player_data))

        return players
