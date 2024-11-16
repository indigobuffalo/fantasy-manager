
from enum import Enum


class Platform(Enum):
    ESPN = "ESPN"
    FANTRAX = "FANTRAX"
    YAHOO = "YAHOO"

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return self.name == other.name
        return NotImplemented

    __hash__ = Enum.__hash__ 
