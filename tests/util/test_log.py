import logging
from unittest.mock import Mock, call
from hamcrest import assert_that, equal_to, has_length, only_contains
import pytest

from fantasy_manager.util.log import (
    align_pairs,
    get_key_adjusted_padding,
    log_line_break,
    log_pairs,
)


@pytest.fixture
def logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def input_tuples():
    yield [("Name", "Owen Nolan"), ("Team", "San Jose Sharks"), ("Number", "11")]


def test_log_line_break(logger):
    spacer, count, lines = "*", 5, 3
    log_line_break(logger, spacer=spacer, count=count, lines=lines)
    assert_that(logger.info.mock_calls, has_length(3))
    assert_that(logger.info.mock_calls, only_contains(call(spacer * count)))


def test_get_key_adjusted_padding(input_tuples):
    longest_label = "Number"
    padding = 1
    expected = padding + len(longest_label)
    assert_that(get_key_adjusted_padding(input_tuples, padding), equal_to(expected))


def test_align_pairs(input_tuples):
    expected = [
        "Name:   Owen Nolan",
        "Team:   San Jose Sharks",
        "Number: 11",
    ]
    assert_that(align_pairs(input_tuples), equal_to(expected))


def test_log_pairs(logger, input_tuples):
    input_tuples.append(("Contract", None))
    expected = [
        "------------------------------------------------------------",
        "Name:     Owen Nolan",
        "Team:     San Jose Sharks",
        "Number:   11",
        "Contract: -",
        "------------------------------------------------------------",
    ]
    log_pairs(logger, input_tuples)
    assert_that(logger.info.mock_calls, equal_to([call(line) for line in expected]))
