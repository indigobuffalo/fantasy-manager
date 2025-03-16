"""File for common testing utilities"""


from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from fantasy_manager.client.base import BaseFantasyClient
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.model.enums.player_status import PlayerStatus
from fantasy_manager.model.enums.position import Position, PositionType
from fantasy_manager.model.league import League
from fantasy_manager.model.player import NhlPlayer, PlayerName
from fantasy_manager.model.team import Team


FROZEN_TIME = datetime(2025, 1, 1, 0, 0, 0)


FROZEN_TIME_PACIFIC = FROZEN_TIME.astimezone(ZoneInfo("America/Los_Angeles"))


NHL_PLAYER_ACTIVE_ONE = NhlPlayer(
    player_id=1,
    name=PlayerName(first="Owen", last="Nolan", full="Owen Nolan"),
    position_type=PositionType.SKATER,
    eligible_positions=[Position.RW, Position.UTIL],
    team="San Jose Sharks",
    team_abbr="SJS",
)


NHL_PLAYER_ACTIVE_TWO = NhlPlayer(
    player_id=2,
    name=PlayerName(first="Joe", last="Pavelski", full="Joe Pavelski"),
    position_type=PositionType.SKATER,
    eligible_positions=[Position.C, Position.RW, Position.UTIL],
    team="San Jose Sharks",
    team_abbr="SJS",
)


NHL_PLAYER_DTD = NhlPlayer(
    player_id=3,
    name=PlayerName(first="Tomas", last="Hertl", full="Tomas Hertl"),
    position_type=PositionType.SKATER,
    eligible_positions=[Position.C, Position.LW, Position.UTIL],
    team="San Jose Sharks",
    team_abbr="SJS",
    status=PlayerStatus.DTD,
)


NHL_PLAYER_IR = NhlPlayer(
    player_id=4,
    name=PlayerName(first="Joe", last="Thornton", full="Joe Thornton"),
    position_type=PositionType.SKATER,
    eligible_positions=[Position.C, Position.UTIL, Position.IR],
    team="San Jose Sharks",
    team_abbr="SJS",
    status=PlayerStatus.IR,
)


NHL_PLAYER_O = NhlPlayer(
    player_id=5,
    name=PlayerName(first="Patrick", last="Marleau", full="Patrick Marleau"),
    position_type=PositionType.SKATER,
    eligible_positions=[Position.C, Position.UTIL],
    team="San Jose Sharks",
    team_abbr="SJS",
)


@pytest.fixture
def mock_client():
    def get_player_by_id_side_effect(player_id: int):
        match player_id:
            case 1:
                return NHL_PLAYER_ACTIVE_ONE
            case 2:
                return NHL_PLAYER_ACTIVE_TWO
            case 3:
                return NHL_PLAYER_DTD
            case 4:
                return NHL_PLAYER_IR
            case 5:
                return NHL_PLAYER_O

    client = Mock(spec=BaseFantasyClient)
    client.get_player_by_id = Mock(side_effect=get_player_by_id_side_effect)
    client.refresh = Mock()
    yield client


@pytest.fixture
def frozen_time():
    with freeze_time(FROZEN_TIME_PACIFIC):
        yield FROZEN_TIME_PACIFIC


@pytest.fixture
def mock_config():
    config = Mock(spec=FantasyConfig)
    config.PRE_FLIGHT_CHECK_SECS = 10
    config.ADD_PLAYER_TIMEOUT_SECONDS = 1
    config.ADD_PLAYER_POLL_SECONDS = 0.2
    yield config


@pytest.fixture
def mock_league():
    yield League(
        id="123",
        key="league_key",
        locked_players=(1, 2, 3),
        name="Test League",
        name_abbr="TL",
        platform="Test Platform",
        team_id=1,
        team_name="Test Team",
    )


@pytest.fixture
def mock_team():
    team = Mock(spec=Team)
    team.has_player = Mock(return_value=False)
    yield team
