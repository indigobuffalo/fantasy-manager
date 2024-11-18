from enum import Enum
from pathlib import Path

from model.enums.platform_url import PlatformUrl


class Platform(Enum):
    ESPN = "ESPN"
    FANTRAX = "FANTRAX"
    YAHOO = "YAHOO"

    def get_url(self, key: PlatformUrl) -> str:
        """Retrieve a specific URL by PlatformUrl key."""
        platform_urls = PLATFORM_URLS.get(self, {})
        url = platform_urls.get(key)
        if not url:
            raise KeyError(f"No URL found for key '{key}' in platform '{self.name}'.")
        return url

    def get_all_urls(self) -> dict[PlatformUrl, str]:
        """Retrieve all URLs for this platform."""
        PLATFORM_URLS.get(self, {}).items()


PLATFORM_URLS = {
    Platform.ESPN: {
        PlatformUrl.FANTASY: "http://todo.com",
        PlatformUrl.GENERAL_NHL: "http://todo.com",
    },
    Platform.FANTRAX: {
        PlatformUrl.FANTASY: "http://todo.com",
        PlatformUrl.GENERAL_NHL: "http://todo.com",
    },
    Platform.YAHOO: {
        PlatformUrl.FANTASY: "https://hockey.fantasysports.yahoo.com/hockey",
        PlatformUrl.GENERAL_NHL: "https://sports.yahoo.com/nhl",
    }
}
