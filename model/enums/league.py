from enum import Enum
from dataclasses import dataclass


class League(Enum):
    KKUPFL = 'KKUPFL'
    PUCKIN_AROUND = 'PA'

    def __str__(self):
        return self.value.name
