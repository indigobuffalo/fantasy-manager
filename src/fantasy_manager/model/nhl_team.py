from __future__ import annotations
from typing import Optional

from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class NhlTeam:
    abbr: str
    name: str
    team_id: int

    def __str__(self):
        return self.name
