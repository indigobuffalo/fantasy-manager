import os
from pathlib import Path
import json
from model.league_data import LeagueData
from model.enums.platform import Platform
from model.enums.platform_url import PlatformUrl


class FantasyConfig:
    """Application configuration, including dynamic season-based paths."""

    # Load the season from environment variables or default to "2024_2025"
    SEASON = os.getenv("FANTASY_SEASON", "2024_2025")

    @staticmethod
    def get_url(platform: Platform, key: PlatformUrl) -> str:
        """Retrieve a specific URL for a platform by PlatformUrl key."""
        if not isinstance(platform, Platform):
            raise ValueError(f"Invalid platform: {platform}")
        if not isinstance(key, PlatformUrl):
            raise ValueError(f"Invalid URL key: {key}")
        return platform.get_url(key)

    @staticmethod
    def get_all_urls(platform: Platform) -> dict[PlatformUrl, str]:
        """Retrieve all URLs for a given platform."""
        if not isinstance(platform, Platform):
            raise ValueError(f"Invalid platform: {platform}")
        return platform.get_all_urls()

    @classmethod
    def get_league_data(cls, league_name: str) -> LeagueData:
        """Load league-specific configuration on demand, considering the current season."""
        config_dir = Path("config/data") / cls.SEASON
        league_file = config_dir / f"leagues/{league_name.upper()}.json"

        if not league_file.exists():
            raise KeyError(f"No configuration file found for league: {league_name} in season {cls.SEASON}")

        with open(league_file) as f:
            league_data = json.load(f)
            return LeagueData(**league_data)