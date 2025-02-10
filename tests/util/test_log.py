import logging
import pytest

from fantasy_manager.util.log import (
    align_pairs,
    get_key_adjusted_padding,
    log_line_break,
    log_pairs,
)


@pytest.fixture
def logger():
    logger = logging.getLogger("Test Logger")
    logger.setLevel(logging.INFO)
    logger.propagate = True
    yield logger


@pytest.fixture
def caplog_info(caplog, logger):
    with caplog.at_level(logging.INFO, logger=logger.name):
        yield caplog


@pytest.fixture
def input_tuples():
    yield [("Name", "Owen Nolan"), ("Team", "San Jose Sharks"), ("Number", "11")]


def test_log_line_break(caplog_info, logger):
    spacer, count, lines = "*", 5, 3
    log_line_break(logger, spacer=spacer, count=count, lines=lines)
    assert len(caplog_info.messages) == 3
    assert all(msg == spacer * count for msg in caplog_info.messages)


def test_get_key_adjusted_padding(input_tuples):
    longest_label = "Number"
    padding = 1
    expected = padding + len(longest_label)
    assert get_key_adjusted_padding(input_tuples, padding) == expected


def test_align_pairs(input_tuples):
    expected = [
        "Name:   Owen Nolan",
        "Team:   San Jose Sharks",
        "Number: 11",
    ]
    assert align_pairs(input_tuples) == expected


def test_log_pairs(caplog, logger, input_tuples):
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
    assert caplog.messages == expected
