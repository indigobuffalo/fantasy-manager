from datetime import date, datetime, timedelta
import zoneinfo
from unittest.mock import Mock, patch

import pytest

from conftest import *
from fantasy_manager.exceptions import InputError
from fantasy_manager.model.enums.position import Position, PositionType
from fantasy_manager.model.league import League
from fantasy_manager.model.player import LineupPlayer, PlayerName
from fantasy_manager.model.team import Team
from fantasy_manager.service.lineup import LineupService


# Production loads leagues via League.from_dict, which keys roster_configuration
# by Position enum; the shared mock_league fixture uses string keys, so build a
# correctly-typed league here for the slot-count validation to work against.
LEAGUE = League(
    id="123",
    key="league_key",
    locked_players=(1, 2, 3),
    name="Test League",
    name_abbr="TL",
    platform="Test Platform",
    team_id=1,
    team_name="Test Team",
    roster_configuration={
        Position.C: 2,
        Position.LW: 2,
        Position.RW: 2,
        Position.D: 4,
        Position.G: 2,
        Position.UTIL: 2,
        # BN is deliberately tiny so the bench-exemption tests can exceed it and
        # prove the bench is not count-validated (real leagues configure more).
        Position.BN: 1,
        Position.IR_PLUS: 2,
    },
)


PACIFIC = zoneinfo.ZoneInfo("US/Pacific")
NOW = datetime(2026, 1, 14, 12, 0, 0, tzinfo=PACIFIC)
LINEUP_DATE = date(2026, 1, 15)
# A start far enough in the future that _log_lineup_inputs won't prompt.
FUTURE_START = NOW + timedelta(hours=1)


def _lineup_player(player_id, full, eligible, selected):
    return LineupPlayer(
        player_id=player_id,
        name=PlayerName(full=full),
        position_type=PositionType.SKATER,
        eligible_positions=eligible,
        selected_position=selected,
    )


# Nolan: RW/UTIL (benched), Pavelski: C, Hertl: LW — all UTIL-eligible.
ROSTER = [
    _lineup_player(1, "Owen Nolan", [Position.RW, Position.UTIL], Position.BN),
    _lineup_player(
        2, "Joe Pavelski", [Position.C, Position.RW, Position.UTIL], Position.C
    ),
    _lineup_player(
        3, "Tomas Hertl", [Position.C, Position.LW, Position.UTIL], Position.LW
    ),
]
TEAM = Team(
    team_id="1",
    team_key="league_key.t.1",
    name="Test Team",
    league_id="123",
    # convert_to_int only coerces str input, so pass "0" not 0.
    faab_balance="0",
    roster=ROSTER,
)


@pytest.fixture
def lineup_svc(mock_config, mock_client):
    mock_client.get_team.return_value = TEAM
    yield LineupService(
        league=LEAGUE,
        fantasy_client=mock_client,
        nhl_client=Mock(),
        config=mock_config,
    )


@patch("fantasy_manager.service.lineup.sleep_until")
@patch("fantasy_manager.service.lineup.now_pacific")
def test_set_lineup_overlays_and_submits_full_lineup(
    mock_now, mock_sleep, lineup_svc, mock_client
):
    mock_now.return_value = NOW
    changes = [{"player_id": 1, "position": "RW"}]

    lineup_svc.set_lineup(changes, LINEUP_DATE, FUTURE_START)

    mock_client.set_lineup.assert_called_once()
    lineup_arg, date_arg = mock_client.set_lineup.call_args.args
    assert date_arg == LINEUP_DATE
    assert lineup_arg.day == LINEUP_DATE
    # Full roster submitted: player 1 moved to RW, others left as-is.
    by_id = {p.player_id: p.selected_position for p in lineup_arg.players}
    assert by_id == {1: Position.RW, 2: Position.C, 3: Position.LW}
    mock_sleep.assert_called_once()


@patch("fantasy_manager.service.lineup.confirm_proceed")
@patch("fantasy_manager.service.lineup.sleep_until")
@patch("fantasy_manager.service.lineup.now_pacific")
def test_set_lineup_confirms_when_immediate(
    mock_now, mock_sleep, mock_confirm, lineup_svc
):
    mock_now.return_value = NOW
    past_start = NOW - timedelta(seconds=1)

    lineup_svc.set_lineup([{"player_id": 1, "position": "RW"}], LINEUP_DATE, past_start)

    mock_confirm.assert_called_once()


@patch("fantasy_manager.service.lineup.confirm_proceed")
@patch("fantasy_manager.service.lineup.sleep_until")
@patch("fantasy_manager.service.lineup.now_pacific")
def test_set_lineup_future_start_does_not_confirm(
    mock_now, mock_sleep, mock_confirm, lineup_svc
):
    mock_now.return_value = NOW

    lineup_svc.set_lineup(
        [{"player_id": 1, "position": "RW"}], LINEUP_DATE, FUTURE_START
    )

    mock_confirm.assert_not_called()


@patch("fantasy_manager.service.lineup.sleep_until")
@patch("fantasy_manager.service.lineup.now_pacific")
def test_set_lineup_bench_slot_always_allowed(
    mock_now, mock_sleep, lineup_svc, mock_client
):
    mock_now.return_value = NOW
    # Pavelski isn't "eligible" for BN, but benching is always permitted.
    lineup_svc.set_lineup(
        [{"player_id": 2, "position": "BN"}], LINEUP_DATE, FUTURE_START
    )

    lineup_arg, _ = mock_client.set_lineup.call_args.args
    by_id = {p.player_id: p.selected_position for p in lineup_arg.players}
    assert by_id[2] == Position.BN


def test_set_lineup_empty_changes_raises(lineup_svc):
    with pytest.raises(InputError):
        lineup_svc.set_lineup([], LINEUP_DATE, FUTURE_START)


def test_set_lineup_unknown_player_raises(lineup_svc):
    with pytest.raises(InputError):
        lineup_svc.set_lineup(
            [{"player_id": 999, "position": "C"}], LINEUP_DATE, FUTURE_START
        )


def test_set_lineup_invalid_position_raises(lineup_svc):
    with pytest.raises(InputError):
        lineup_svc.set_lineup(
            [{"player_id": 1, "position": "XX"}], LINEUP_DATE, FUTURE_START
        )


def test_set_lineup_ineligible_position_raises(lineup_svc):
    # Nolan is eligible only for RW/UTIL, not D.
    with pytest.raises(InputError):
        lineup_svc.set_lineup(
            [{"player_id": 1, "position": "D"}], LINEUP_DATE, FUTURE_START
        )


def test_set_lineup_too_many_in_slot_raises(lineup_svc):
    # UTIL has 2 slots; assigning all three players to UTIL overflows it.
    changes = [
        {"player_id": 1, "position": "UTIL"},
        {"player_id": 2, "position": "UTIL"},
        {"player_id": 3, "position": "UTIL"},
    ]
    with pytest.raises(InputError):
        lineup_svc.set_lineup(changes, LINEUP_DATE, FUTURE_START)


def test_set_lineup_too_many_in_ir_plus_raises(lineup_svc):
    # IR+ is a capped slot (2 here): a third IR+ assignment must be rejected,
    # even though eligibility is bypassed for IR slots.
    changes = [
        {"player_id": 1, "position": "IR+"},
        {"player_id": 2, "position": "IR+"},
        {"player_id": 3, "position": "IR+"},
    ]
    with pytest.raises(InputError):
        lineup_svc.set_lineup(changes, LINEUP_DATE, FUTURE_START)


@patch("fantasy_manager.service.lineup.sleep_until")
@patch("fantasy_manager.service.lineup.now_pacific")
def test_set_lineup_ir_plus_within_limit_allowed(
    mock_now, mock_sleep, lineup_svc, mock_client
):
    mock_now.return_value = NOW
    # Two IR+ assignments fit the 2 configured IR+ slots.
    lineup_svc.set_lineup(
        [{"player_id": 1, "position": "IR+"}, {"player_id": 2, "position": "IR+"}],
        LINEUP_DATE,
        FUTURE_START,
    )

    lineup_arg, _ = mock_client.set_lineup.call_args.args
    by_id = {p.player_id: p.selected_position for p in lineup_arg.players}
    assert by_id[1] == Position.IR_PLUS
    assert by_id[2] == Position.IR_PLUS


def test_set_lineup_bench_not_count_capped(lineup_svc, mock_client):
    # BN is the overflow slot and is intentionally not count-validated; a roster
    # carrying more than the nominal BN count must still be accepted.
    with patch("fantasy_manager.service.lineup.sleep_until"), patch(
        "fantasy_manager.service.lineup.now_pacific", return_value=NOW
    ):
        lineup_svc.set_lineup(
            [
                {"player_id": 1, "position": "BN"},
                {"player_id": 2, "position": "BN"},
                {"player_id": 3, "position": "BN"},
            ],
            LINEUP_DATE,
            FUTURE_START,
        )
    mock_client.set_lineup.assert_called_once()
