import os
import json
from pathlib import Path
from typing import Any
import yaml

from dotenv import load_dotenv

from model.league_data import LeagueData
from model.enums.platform import Platform
from model.enums.platform_url import PlatformUrl


load_dotenv()
CONFIG_DIR = Path(__file__).parent.absolute()


class FantasyConfig:
    """Application configuration, including dynamic season-based paths."""

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
        }
    }

    # Load the season from environment variables or default to "2024_2025"
    SEASON = os.getenv("FANTASY_SEASON", "2024_2025")

    @classmethod
    def get_platform_url(cls, platform: Platform, key: PlatformUrl) -> str:
        """Retrieve a specific URL for the platform and key."""
        platform_urls = cls.PLATFORM_URLS.get(platform, {})
        url = platform_urls.get(key)
        if not url:
            raise KeyError(f"No URL found for key '{key}' in platform '{platform.name}'.")
        return url

    @staticmethod
    def get_cookie(platform: Platform) -> str:
        """Retrieve cookies for the given platform from environment variables."""
        cookie_env_var = f"{platform.name}_COOKIE"
        cookie = os.getenv(cookie_env_var)
        if not cookie:
            raise ValueError(f"No cookie set for platform '{platform.name}'. Expected env var: {cookie_env_var}")
        return cookie

    @staticmethod
    def get_crumb(platform: Platform) -> str:
        """Retrieve crumb for the given platform from environment variables."""
        crumb_env_var = f"{platform.name}_CRUMB"
        crumb = os.getenv(crumb_env_var)
        if not crumb:
            raise ValueError(f"No crumb set for platform '{platform.name}'. Expected env var: {crumb_env_var}")
        return crumb

    @classmethod
    def get_league_data(cls, league_name: str) -> LeagueData:
        """Load league-specific configuration on demand, considering the current season."""
        league_file = CONFIG_DIR / f"data/season/{cls.SEASON}/league/{league_name.lower()}.json"

        if not league_file.exists():
            raise KeyError(f"No configuration file found for league: {league_name} in season {cls.SEASON}")

        with open(league_file) as f:
            json_data = json.load(f)
            return LeagueData.from_dict(json_data)

    @classmethod
    def get_roster_data(cls, league_name: str, roster_name: str) -> dict[str, Any]:
        """
        Load league-specific roster data on demand, considering the current season.
        
        Args:
            league_name (str): The name of the league.
            roster_name (str): The name of the roster.
        
        Returns:
            Dict[str, Any]: The loaded roster data.
        
        Raises:
            FileNotFoundError: If the roster file does not exist.
            ValueError: If the loaded data is invalid or improperly formatted.
        """
        roster_file = CONFIG_DIR / f"data/season/{cls.SEASON}/roster/{league_name.lower()}_{roster_name}.yml"
        if not roster_file.exists():
            raise FileNotFoundError(
                f"Roster file '{league_name.lower()}_{roster_name}.yml' not found for season '{cls.SEASON}' "
                f"in directory '{roster_file.parent}'."
            )
        try:
            with open(roster_file, "r") as f:
                yaml_data = yaml.safe_load(f)

            if not isinstance(yaml_data, dict):
                raise ValueError(f"Invalid data format in roster file: {roster_file}. Expected a dictionary.")

            return yaml_data
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file '{roster_file}': {e}")
