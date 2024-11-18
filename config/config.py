import os
import json
from pathlib import Path
from typing import Any

import yaml

from model.league_data import LeagueData
from model.enums.platform import Platform
from model.enums.platform_url import PlatformUrl


CONFIG_DIR = Path(__file__).parent.absolute()


class FantasyConfig:
    """Application configuration, including dynamic season-based paths."""

    # Load the season from environment variables or default to "2024_2025"
    SEASON = os.getenv("FANTASY_SEASON", "2024_2025")

    @staticmethod
    def get_url(platform: Platform, platform_url: PlatformUrl) -> str:
        """Retrieve a specific URL for a platform by PlatformUrl key."""
        if not isinstance(platform, Platform):
            raise ValueError(f"Invalid platform: {platform}")
        if not isinstance(platform_url, PlatformUrl):
            raise ValueError(f"Invalid URL key: {platform_url}")
        return platform.get_url(platform_url)

    @staticmethod
    def get_all_urls(platform: Platform) -> dict[PlatformUrl, str]:
        """Retrieve all URLs for a given platform."""
        if not isinstance(platform, Platform):
            raise ValueError(f"Invalid platform: {platform}")
        return platform.get_all_urls()

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
