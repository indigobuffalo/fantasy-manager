from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import Mock, call, patch

import pytest
from hamcrest import assert_that, equal_to

from conftest import *
from fantasy_manager.model.player import NhlPlayer
from fantasy_manager.exceptions import (
    AlreadyAddedError,
    FantasyUnknownError,
    NotOnRosterError,
    TimeoutExceededError,
)
from fantasy_manager.service.roster import RosterService


ADD_ID = NHL_PLAYER_ACTIVE_ONE.player_id
DROP_ID = NHL_PLAYER_ACTIVE_TWO.player_id


@pytest.fixture
def roster_service(mock_config, mock_league, mock_team, mock_client):
    yield RosterService(
        config=mock_config, league=mock_league, team=mock_team, client=mock_client
    )


def test_check_player_inputs_add_player_already_added(roster_service, mock_team):
    mock_team.has_player.return_value = True
    with pytest.raises(AlreadyAddedError):
        roster_service._check_player_inputs(add_player=Mock(spec=NhlPlayer))


def test_check_player_inputs_drop_player_not_on_roster(roster_service, mock_team):
    mock_team.has_player.return_value = False
    with pytest.raises(NotOnRosterError):
        roster_service._check_player_inputs(drop_player=Mock(spec=NhlPlayer))


def test_get_player_data(roster_service, mock_client):
    player_id = 1
    roster_service.get_player_data(player_id)
    mock_client.get_player_by_id.assert_called_once_with(player_id)


def test_run_preflight_checks(roster_service, mock_client):
    roster_service._check_player_inputs = Mock()

    assert_that(mock_client.refresh.call_count, equal_to(1))

    roster_service.run_preflight_checks(NHL_PLAYER_ACTIVE_ONE, NHL_PLAYER_ACTIVE_TWO)

    assert_that(mock_client.refresh.call_count, equal_to(2))
    roster_service._check_player_inputs.assert_called_once_with(
        add_player=NHL_PLAYER_ACTIVE_ONE, drop_player=NHL_PLAYER_ACTIVE_TWO
    )


@patch("fantasy_manager.service.roster.logger")
@patch("fantasy_manager.service.roster.sleep_until")
def test_prepare_to_execute(mock_sleep_until, mock_logger, roster_service, frozen_time):
    roster_service.run_preflight_checks = Mock()

    start = frozen_time + timedelta(seconds=20)
    preflight_check_dt = start - timedelta(
        seconds=roster_service.cfg.PRE_FLIGHT_CHECK_SECS
    )

    expected_sleep_until_calls = [
        call(preflight_check_dt, mock_logger),
        call(start, mock_logger),
    ]

    roster_service.prepare_to_execute(
        start=start, add_player=NHL_PLAYER_ACTIVE_ONE, drop_player=NHL_PLAYER_DTD
    )

    roster_service.run_preflight_checks.assert_called_once_with(
        NHL_PLAYER_ACTIVE_ONE, NHL_PLAYER_DTD
    )
    assert_that(mock_sleep_until.call_args_list, equal_to(expected_sleep_until_calls))


@patch("fantasy_manager.service.roster.log_pairs")
@patch("fantasy_manager.service.roster.logger")
def test_log_inputs(mock_logger, mock_log_pairs, roster_service, frozen_time):
    start = frozen_time + timedelta(seconds=20)
    pairs = [
        ("League", roster_service.league.name),
        ("Start", f"0 HOURS 0 MINUTES 20 SECONDS"),
        ("Add", f"{NHL_PLAYER_ACTIVE_ONE.name.full}    [1]"),
        ("Drop", f"{NHL_PLAYER_IR.name.full}  [4]"),
    ]
    roster_service.log_inputs(
        start=start, add_player=NHL_PLAYER_ACTIVE_ONE, drop_player=NHL_PLAYER_IR
    )
    mock_log_pairs.assert_called_once_with(logger=mock_logger, tuples=pairs, padding=4)


def test_add_player(roster_service, mock_client, frozen_time):
    roster_service.prepare_to_execute = Mock()
    roster_service.log_inputs = Mock()

    start = frozen_time + timedelta(seconds=20)
    roster_service.add_player(add_id=ADD_ID, start=start)

    mock_client.add_player.assert_called_once_with(add_id=ADD_ID)
    roster_service.prepare_to_execute.assert_called_once_with(
        add_player=NHL_PLAYER_ACTIVE_ONE, start=start
    )
    roster_service.log_inputs.assert_called_once_with(
        start, add_player=NHL_PLAYER_ACTIVE_ONE
    )


def test_add_player_claim(roster_service, mock_client, frozen_time):
    roster_service.prepare_to_execute = Mock()
    roster_service.log_inputs = Mock()

    faab = 10
    start = frozen_time + timedelta(seconds=20)
    roster_service.add_player_claim(ADD_ID, faab, start)
    mock_client.add_player_claim.assert_called_once_with(add_id=ADD_ID, faab=faab)


def test_replace_player(roster_service, mock_client, frozen_time):
    roster_service.prepare_to_execute = Mock()
    roster_service.log_inputs = Mock()

    start = frozen_time + timedelta(seconds=20)
    roster_service.replace_player(ADD_ID, DROP_ID, start)
    mock_client.replace_player.assert_called_once_with(add_id=ADD_ID, drop_id=DROP_ID)


@patch("fantasy_manager.service.roster.now_pacific")
def test_add_player_timeout(mock_now_pacific, roster_service, mock_client, frozen_time):
    roster_service.log_inputs = Mock()
    roster_service.prepare_to_execute = Mock()
    roster_service.refresh_team = Mock()
    roster_service.team.has_player = Mock(return_value=False)

    start = frozen_time + timedelta(seconds=20)

    # Simulate the passage of time
    mock_now_pacific.side_effect = [
        start + timedelta(seconds=i)
        for i in range(roster_service.cfg.ADD_PLAYER_TIMEOUT_SECONDS + 2)
    ]

    mock_client.add_player.side_effect = Exception("Simulated failure")

    with pytest.raises(TimeoutExceededError):
        roster_service.add_player(ADD_ID, start)

    mock_client.add_player.assert_called_once_with(add_id=ADD_ID)
    roster_service.log_inputs.assert_called_once_with(
        start, add_player=roster_service.get_player_data(ADD_ID)
    )
    roster_service.prepare_to_execute.assert_called_once_with(
        add_player=roster_service.get_player_data(ADD_ID), start=start
    )


# TODO: Fix this test
# def test_replace_player_timeout(roster_service, mock_client, frozen_time):
#    roster_service.prepare_to_execute = Mock()
#    roster_service.log_inputs = Mock()
#    roster_service.refresh_team = Mock()
#    roster_service.team.has_player = Mock(return_value=False)
#
#    start = frozen_time + timedelta(seconds=20)
#    end = start + timedelta(seconds=roster_service.cfg.TIMEOUT_SECONDS)
#
#    # Simulate the passage of time
#    with patch('fantasy_manager.service.roster.now_pacific', return_value=end):
#        with pytest.raises(FantasyUnknownError):
#            roster_service.replace_player(ADD_ID, DROP_ID, start)
#
#    mock_client.replace_player.assert_called_once_with(add_id=ADD_ID, drop_id=DROP_ID)
#    roster_service.refresh_team.assert_called_once()
#    roster_service.team.has_player.assert_called_once_with(roster_service.get_player_data(ADD_ID))

# TODO: Fix this test
# @patch('fantasy_manager.service.roster.now_pacific')
# def test_replace_player_unsuccessful(mock_now_pacific, roster_service, mock_client, frozen_time):
#    roster_service.prepare_to_execute = Mock()
#    roster_service.log_inputs = Mock()
#    roster_service.refresh_team = Mock()
#    roster_service.team.has_player = Mock(return_value=False)
#
#    start = frozen_time + timedelta(seconds=20)
#    end = start + timedelta(seconds=roster_service.cfg.TIMEOUT_SECONDS)
#
#    # Simulate the passage of time
#    mock_now_pacific.side_effect = [start + timedelta(seconds=i) for i in range(roster_service.cfg.TIMEOUT_SECONDS + 1)]
#
#    with pytest.raises(FantasyUnknownError):
#        roster_service.replace_player(ADD_ID, DROP_ID, start)
#
#    mock_client.replace_player.assert_called_once_with(add_id=ADD_ID, drop_id=DROP_ID)
#    roster_service.refresh_team.assert_called_once()
#    roster_service.team.has_player.assert_called_once_with(roster_service.get_player_data(ADD_ID))


def test_replace_player_claim(roster_service, mock_client, frozen_time):
    roster_service.prepare_to_execute = Mock()
    roster_service.log_inputs = Mock()

    faab = 10
    start = frozen_time + timedelta(seconds=20)
    roster_service.replace_player_claim(ADD_ID, DROP_ID, faab, start)
    mock_client.replace_player_claim.assert_called_once_with(
        add_id=ADD_ID, drop_id=DROP_ID, faab=faab
    )


def test_drop_player(roster_service, mock_client, frozen_time):
    roster_service.prepare_to_execute = Mock()
    roster_service.log_inputs = Mock()
    roster_service.refresh_team = Mock()
    roster_service.team.has_player = Mock(return_value=False)

    start = frozen_time + timedelta(seconds=20)
    roster_service.drop_player(DROP_ID, start)
    mock_client.drop_player.assert_called_once_with(DROP_ID)


def test_drop_player_unsuccessful(roster_service, mock_client, frozen_time):
    roster_service.prepare_to_execute = Mock()
    roster_service.log_inputs = Mock()
    roster_service.refresh_team = Mock()
    roster_service.team.has_player = Mock(return_value=True)

    start = frozen_time + timedelta(seconds=20)
    with pytest.raises(FantasyUnknownError):
        roster_service.drop_player(DROP_ID, start)
    mock_client.drop_player.assert_called_once_with(DROP_ID)
