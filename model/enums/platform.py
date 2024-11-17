from enum import Enum
from model.enums.platform_url import PlatformUrl


class Platform(Enum):
    ESPN = "ESPN"
    FANTRAX = "FANTRAX"
    YAHOO = "YAHOO"

    BASE_URLS = {
        "ESPN": {
            PlatformUrl.FANTASY: "TODO",
            PlatformUrl.GENERAL_NHL: "TODO"
        },
        "FANTRAX": {
            PlatformUrl.FANTASY: "TODO",
            PlatformUrl.GENERAL_NHL: "TODO"
        },
        "YAHOO": {
            PlatformUrl.FANTASY: "https://hockey.fantasysports.yahoo.com/hockey",
            PlatformUrl.GENERAL_NHL: "https://sports.yahoo.com/nhl"
        }
    }

    def get_url(self, key: PlatformUrl) -> str:
        """Retrieve a specific URL by PlatformUrl key."""
        platform_urls = self.BASE_URLS.get(self.name, {})
        url = platform_urls.get(key)
        if not url:
            raise KeyError(f"No URL found for key '{key}' in platform '{self.name}'.")
        return url

    def get_all_urls(self) -> dict[PlatformUrl, str]:
        """Retrieve all URLs for this platform."""
        return self.BASE_URLS.get(self.name, {})
