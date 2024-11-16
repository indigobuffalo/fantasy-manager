from model.enums.league import League
from model.enums.platform import Platform
from model.league_data import LeagueData


LEAGUES = {
    League.PUCKIN_AROUND: LeagueData(
        id="31175",
        name="PUCKIN' AROUND",
        platform=Platform.YAHOO,
        team_id=1,
        team_name="Larkin Up the Wrong Tree",
        locked_players=["6744", "6751", "6877"] # Eichel, Meier, Kaprizov
    ),
    League.KKUPFL: LeagueData(
       id="88127",
       name="KKUPFL - T2 SAN JOSE",
       platform=Platform.YAHOO,
       team_id=7,
       team_name="Larkin Up the Wrong Tree",
       locked_players=["5425", "6758", "8290"] # Kucherov, Barzal, Boldy
    )
}
