from dataclasses import dataclass
from typing import Optional

from config.data.leagues._current_leagues import LEAGUES
from model.enums.league import League
from model.enums.platform import Platform
from model.league_data import LeagueData


class FantasyConfig:
    BASE_URLS = {
        Platform.ESPN: "TODO",
        Platform.FANTRAX: "TODO",
        Platform.YAHOO: "https://hockey.fantasysports.yahoo.com/hockey"
    }

    LEAGUES = LEAGUES

    @classmethod
    def get_base_url(cls, platform: Platform) -> Optional[str]:
        if not isinstance(platform, Platform):
            raise ValueError(f"Invalid platform: {platform}")
        return cls.BASE_URLS.get(platform, None)

    @classmethod
    def get_league_data(cls, league_name: str) -> Optional[LeagueData]:
        return cls.LEAGUES.get(League(league_name.upper()), None)
