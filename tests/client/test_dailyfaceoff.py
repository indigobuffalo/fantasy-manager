import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
from hamcrest import (
    assert_that,
    contains_exactly,
    contains_string,
    empty,
    equal_to,
    greater_than,
    has_length,
    is_,
    none,
)

from fantasy_manager.client.news.dailyfaceoff import (
    DailyFaceoffClient,
    parse_player_name,
)
from fantasy_manager.exceptions import NewsSourceUnavailableError
from fantasy_manager.model.lines import GoalieConfidence, InjuriesFreshness


FIXTURE = Path(__file__).parent / "fixtures" / "dailyfaceoff_lines.json"


@pytest.fixture
def raw_feed() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def feed(raw_feed):
    return DailyFaceoffClient.parse(raw_feed)


def _mock_session(json_payload=None, raise_on_get=None, raise_on_json=None):
    """Build a mock requests.Session for fetch_lines tests."""
    session = Mock(spec=requests.Session)
    if raise_on_get is not None:
        session.get = Mock(side_effect=raise_on_get)
        return session
    resp = Mock()
    resp.raise_for_status = Mock()
    resp.json = (
        Mock(side_effect=raise_on_json)
        if raise_on_json
        else Mock(return_value=json_payload)
    )
    session.get = Mock(return_value=resp)
    return session


# --- parse_player_name ------------------------------------------------------


def test_parse_player_name_strips_accents():
    name = parse_player_name("TIM STÜTZLE")

    assert_that(name.full, equal_to("Tim Stützle"))
    assert_that(name.first, equal_to("Tim"))
    assert_that(name.last, equal_to("Stützle"))
    assert_that(name.ascii_first, equal_to("tim"))
    assert_that(name.ascii_last, equal_to("stutzle"))


def test_parse_player_name_handles_hyphenated_first_name():
    name = parse_player_name("UKKO-PEKKA LUUKKONEN")

    assert_that(name.ascii_first, equal_to("ukko-pekka"))
    assert_that(name.ascii_last, equal_to("luukkonen"))


def test_parse_player_name_collapses_whitespace_and_single_token():
    name = parse_player_name("  OVECHKIN  ")

    assert_that(name.full, equal_to("Ovechkin"))
    assert_that(name.ascii_last, is_(none()))
    assert_that(name.ascii_first, equal_to("ovechkin"))


# --- parse ------------------------------------------------------------------


def test_parse_reads_feed_metadata(feed):
    assert_that(feed.source, equal_to("dailyfaceoff.com"))
    assert_that(
        feed.updated_at,
        equal_to(datetime(2026, 3, 2, 16, 34, 5, tzinfo=timezone.utc)),
    )
    assert_that(feed.injuries_status, equal_to(InjuriesFreshness.FRESH))
    assert_that(
        feed.injuries_updated_at,
        equal_to(datetime(2026, 3, 2, 16, 34, 5, tzinfo=timezone.utc)),
    )


def test_parse_maps_team_identity(feed):
    ott = feed.teams["ottawa-senators"]

    assert_that(ott.team_abbr, equal_to("OTT"))
    assert_that(ott.team_name, equal_to("Ottawa Senators"))


def test_parse_unknown_slug_has_no_abbr(feed):
    isotopes = feed.teams["springfield-isotopes"]

    assert_that(isotopes.team_abbr, is_(none()))
    assert_that(isotopes.team_name, is_(none()))
    assert_that(isotopes.forward_lines, is_(empty()))


def test_parse_forward_lines_in_order(feed):
    ott = feed.teams["ottawa-senators"]

    assert_that(ott.forward_lines, has_length(2))
    first_line = [p.full for p in ott.forward_lines[0]]
    assert_that(
        first_line, contains_exactly("Tim Stützle", "Josh Norris", "Claude Giroux")
    )


def test_parse_defense_pairs_in_order(feed):
    ott = feed.teams["ottawa-senators"]

    assert_that(ott.defense_pairs, has_length(2))
    assert_that(ott.defense_pairs[0][0].ascii_last, equal_to("sanderson"))


def test_parse_goalies_starter_first_and_unconfirmed(feed):
    goalies = feed.teams["ottawa-senators"].goalies

    assert_that(goalies, has_length(2))
    assert_that(goalies[0].goalie.full, equal_to("Linus Ullmark"))
    assert_that(goalies[0].is_starter, is_(True))
    assert_that(goalies[1].is_starter, is_(False))
    assert_that(goalies[0].confidence, equal_to(GoalieConfidence.UNCONFIRMED))


def test_parse_power_play_units_pp1_before_pp2(feed):
    pp = feed.teams["ottawa-senators"].power_play_units

    assert_that(pp, has_length(2))
    assert_that(pp[0][0].full, equal_to("Tim Stützle"))
    assert_that(pp[1][0].full, equal_to("Shane Pinto"))


def test_parse_missing_power_play_is_empty(feed):
    buf = feed.teams["buffalo-sabres"]

    assert_that(buf.power_play_units, is_(empty()))


def test_parse_injuries_attached_per_team(feed):
    injuries = feed.teams["ottawa-senators"].injuries

    assert_that(injuries, has_length(2))
    norris = injuries[0]
    assert_that(norris.player.full, equal_to("Josh Norris"))
    assert_that(norris.status, equal_to("Day-To-Day"))
    assert_that(norris.position, equal_to("C"))
    assert_that(norris.description, equal_to("Upper body"))


def test_parse_pk_and_scratches_always_empty_in_v1(feed):
    for team in feed.teams.values():
        assert_that(team.penalty_kill_units, is_(empty()))
        assert_that(team.scratches, is_(empty()))


def test_parse_tolerates_legacy_snapshot_without_injuries_or_pp():
    legacy = {
        "source": "dailyfaceoff.com",
        "updated_at": "2026-03-02 16:34:05 UTC",
        "teams": {
            "boston-bruins": {
                "forwards": [["A B", "C D", "E F"]],
                "defense": [["G H", "I J"]],
                "goalies": [["K L"]],
            }
        },
    }

    feed = DailyFaceoffClient.parse(legacy)

    bos = feed.teams["boston-bruins"]
    assert_that(bos.power_play_units, is_(empty()))
    assert_that(bos.injuries, is_(empty()))
    assert_that(feed.injuries_status, equal_to(InjuriesFreshness.UNAVAILABLE))
    assert_that(feed.injuries_updated_at, is_(none()))


def test_parse_rejects_non_dict_payload():
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient.parse(["not", "a", "dict"])


def test_parse_rejects_payload_without_teams():
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient.parse({"source": "dailyfaceoff.com"})


def test_parse_unknown_injury_status_falls_back_to_unavailable():
    raw = {
        "teams": {},
        "injuries_meta": {"status": "bananas"},
    }

    feed = DailyFaceoffClient.parse(raw)

    assert_that(feed.injuries_status, equal_to(InjuriesFreshness.UNAVAILABLE))


# --- is_stale ---------------------------------------------------------------


def test_is_stale_false_for_recent_feed(feed):
    client = DailyFaceoffClient(stale_after=timedelta(hours=36))
    now = feed.updated_at + timedelta(hours=1)

    assert_that(client.is_stale(feed, now=now), is_(False))


def test_is_stale_true_past_threshold(feed):
    client = DailyFaceoffClient(stale_after=timedelta(hours=36))
    now = feed.updated_at + timedelta(hours=48)

    assert_that(client.is_stale(feed, now=now), is_(True))


def test_is_stale_true_when_timestamp_missing():
    client = DailyFaceoffClient()
    feed = DailyFaceoffClient.parse({"teams": {}})

    assert_that(feed.updated_at, is_(none()))
    assert_that(client.is_stale(feed), is_(True))


# --- fetch_lines ------------------------------------------------------------


def test_fetch_lines_returns_parsed_feed(raw_feed):
    client = DailyFaceoffClient(session=_mock_session(json_payload=raw_feed))

    feed = client.fetch_lines()

    assert_that(len(feed.teams), is_(greater_than(0)))
    assert_that(feed.teams["ottawa-senators"].team_abbr, equal_to("OTT"))


def test_fetch_lines_warns_when_stale(raw_feed, caplog):
    # The fixture's updated_at is far in the past, so the real now is stale.
    client = DailyFaceoffClient(session=_mock_session(json_payload=raw_feed))

    with caplog.at_level("WARNING"):
        client.fetch_lines()

    assert_that(caplog.text, contains_string("stale"))


def test_fetch_lines_raises_on_network_error():
    client = DailyFaceoffClient(
        session=_mock_session(raise_on_get=requests.ConnectionError("boom"))
    )

    with pytest.raises(NewsSourceUnavailableError):
        client.fetch_lines()


def test_fetch_lines_raises_on_malformed_json():
    client = DailyFaceoffClient(
        session=_mock_session(raise_on_json=ValueError("not json"))
    )

    with pytest.raises(NewsSourceUnavailableError):
        client.fetch_lines()
