from fantasy_manager.client.espn import EspnClient
from fantasy_manager.client.fantrax import FantraxClient
from fantasy_manager.client.yahoo import YahooClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.enums.platform import Platform
from fantasy_manager.model.league import League


class ClientFactory:
    @staticmethod
    def get_client(platform: Platform, league: League, config: FantasyConfig):
        match platform:
            case Platform.YAHOO:
                return YahooClient(league=league, config=config)
            # case Platform.ESPN:
            # return EspnClient()
            # case Platform.FANTRAX:
            # return FantraxClient()
            case _:
                raise ValueError(f"No client available for platform: {platform}")
