import json

import pytest
import yaml
from hamcrest import assert_that, equal_to

from fantasy_manager.exceptions import InputError
from fantasy_manager.util.output import (
    OutputFormat,
    parse_output_format,
    serialize,
)


def test_parse_output_format_defaults_to_text_when_none():
    assert_that(parse_output_format(None), equal_to(OutputFormat.TEXT))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("text", OutputFormat.TEXT),
        ("json", OutputFormat.JSON),
        ("yaml", OutputFormat.YAML),
        ("JSON", OutputFormat.JSON),  # case-insensitive
    ],
)
def test_parse_output_format_accepts_known_values(raw, expected):
    assert_that(parse_output_format(raw), equal_to(expected))


def test_parse_output_format_rejects_unknown_value():
    with pytest.raises(InputError):
        parse_output_format("xml")


def test_output_format_is_structured():
    assert_that(OutputFormat.TEXT.is_structured, equal_to(False))
    assert_that(OutputFormat.JSON.is_structured, equal_to(True))
    assert_that(OutputFormat.YAML.is_structured, equal_to(True))


def test_serialize_json_round_trips():
    data = {"leagues": [{"id": "1", "name": "T1 Sweden", "players": []}]}
    assert_that(json.loads(serialize(data, OutputFormat.JSON)), equal_to(data))


def test_serialize_yaml_round_trips():
    data = {"leagues": [{"id": "1", "name": "T1 Sweden", "players": []}]}
    assert_that(yaml.safe_load(serialize(data, OutputFormat.YAML)), equal_to(data))


def test_serialize_rejects_text_format():
    with pytest.raises(ValueError):
        serialize({}, OutputFormat.TEXT)
