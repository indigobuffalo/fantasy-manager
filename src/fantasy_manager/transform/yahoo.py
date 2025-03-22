import copy
from typing import Any

from fantasy_manager.model.dto.team import RawTeamDto


def transform_nhl_raw_games_to_games(raw: dict) -> dict:
    tfm = copy.deepcopy(raw)
    tfm["startTimeUtc"] = tfm.pop("startTimeUTC")
    return tfm


def transform_player_by_id_to_api_player(raw: dict) -> dict:
    tfm = copy.deepcopy(raw)
    tfm["eligible_positions"] = [
        p["position"].upper() for p in tfm["eligible_positions"]
    ]
    tfm["team"] = {
        "name": tfm["editorial_team_full_name"].title(),
        "abbr": tfm["editorial_team_abbr"].upper(),
        "team_id": tfm["editorial_team_key"].split(".")[-1],
    }
    tfm["team_abbr"] = tfm["editorial_team_abbr"]
    tfm["status"] = tfm.get("status", "")
    return tfm


def transform_yfa_team_data_to_team(dto: RawTeamDto) -> dict[str, Any]:
    """Transform a RawTeamDto into the format required by the Team model."""
    return {
        **dto.additional_data,
        "league_id": dto.league_id,
        "roster": _transform_roster(dto.roster),
    }


def _transform_roster(roster: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform raw roster data."""
    return [
        {
            **player,
            "name": {"full": player["name"]},
            "eligible_positions": [pos.upper() for pos in player["eligible_positions"]],
            "selected_position": player["selected_position"].upper(),
            "status": player.get("status", ""),
        }
        for player in roster
    ]
