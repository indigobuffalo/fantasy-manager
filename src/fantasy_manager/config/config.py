import os
import json
from pathlib import Path
from typing import Any, Optional
import yaml

from dotenv import find_dotenv, load_dotenv

from fantasy_manager.exceptions import InvalidLeagueError
from fantasy_manager.model.league import League
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.enums.platform_url import PlatformUrl
from fantasy_manager.model.lineup import Lineup


# Resolve .env independently of how the CLI is invoked: prefer the nearest .env
# walking up from the current working directory (so running inside a worktree
# uses that worktree's .env), then fall back to the anchored canonical location.
load_dotenv(
    find_dotenv(usecwd=True) or Path.home() / ".config" / "fantasy-manager" / ".env"
)
CONFIG_DIR = Path(__file__).parent.absolute()


class FantasyConfig:
    """Application configuration, including dynamic season-based paths."""

    VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    if LOG_LEVEL not in VALID_LOG_LEVELS:
        LOG_LEVEL = "INFO"

    # How far before the target time to wake, re-authenticate, and validate
    # inputs so the transaction fires clean exactly on time.
    PRE_FLIGHT_CHECK_SECS = int(os.getenv("PRE_FLIGHT_CHECK_SECS", 30))
    # How far before the target time the first write actually fires, so the
    # retry loop is already hammering as the transaction window opens.
    FIRE_EARLY_BUFFER_SECS = float(os.getenv("FIRE_EARLY_BUFFER_SECS", 0.2))

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
    SEASON = os.getenv("FANTASY_SEASON", "2026_2027")
    YAHOO_CREDS_FILE = os.getenv("YAHOO_CREDS_FILE")
    YAHOO_COOKIE = os.getenv("YAHOO_COOKIE")  # browser-harvested; used by the cookie write transport
    YAHOO_CRUMB = os.getenv("YAHOO_CRUMB")  # browser-harvested; used by the cookie write transport
    # When set, skip the startup OAuth read probe and route reads straight to the
    # cookie transport. Useful when OAuth reads are known-gated (Yahoo hasn't
    # granted the app Fantasy Sports read scope) so there's no point probing.
    YAHOO_FORCE_COOKIE_READS = os.getenv("YAHOO_FORCE_COOKIE_READS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    YEAR = os.getenv("YEAR", "2026")

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
    def get_player_rankings(cls, league_abbr: str) -> dict[int, int]:
        """Get player rankings for the specified league.

        Args:
            league_abbr (str): Abbreviated name of the league.

        Raises:
            FileNotFoundError: Error raised if the rankings file is not found.
            ValueError: Error raised if the rankings file is not a valid YAML file.

        Returns:
            dict[int, int]: A mapping of player IDs to their rankings.
        """
        rankings_file = (
            CONFIG_DIR / f"data/season/{cls.SEASON}/rankings/{league_abbr.lower()}.yml"
        )
        if not rankings_file.exists():
            raise FileNotFoundError(f"Rankings file not found: '{rankings_file}'.")

        try:
            with open(rankings_file, "r") as f:
                data = yaml.safe_load(f)
                if "player_rankings" not in data:
                    raise ValueError(
                        f"Rankings file '{rankings_file}' does not contain a 'player_rankings' key."
                    )
                return data["player_rankings"]
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file '{rankings_file}': {e}")
