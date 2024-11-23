from client.espn import EspnClient
from client.fantrax import FantraxClient
from client.yahoo import YahooClient
from config.config import FantasyConfig
from model.enums.platform import Platform
from model.league import League


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
