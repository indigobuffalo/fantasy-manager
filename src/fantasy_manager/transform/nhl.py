import copy


def _transform_team(team: dict) -> dict:
    return {
        "abbr": team["abbrev"].upper(),
        "name": team["commonName"]["default"].title(),
        "team_id": team["id"],
    }


def transform_nhl_raw_games_to_games(raw: dict) -> dict:
    tfm = copy.deepcopy(raw)
    tfm["start_time_utc"] = tfm.pop("startTimeUTC")
    tfm["away_team"] = _transform_team(tfm.pop("awayTeam"))
    tfm["home_team"] = _transform_team(tfm.pop("homeTeam"))
    return tfm
