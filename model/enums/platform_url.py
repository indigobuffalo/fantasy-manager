from enum import Enum


class PlatformUrl(Enum):
    FANTASY = "fantasy_hockey"
    GENERAL_NHL = "general_nhl"

    def __str__(self):
        return self.value
