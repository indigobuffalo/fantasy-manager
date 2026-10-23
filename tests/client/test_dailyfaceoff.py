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
    has_length,
    is_,
    none,
)

from fantasy_manager.client.news.dailyfaceoff import (
    BASE_URL,
    DailyFaceoffClient,
    parse_player_name,
)
from fantasy_manager.exceptions import NewsSourceUnavailableError
from fantasy_manager.model.lines import (
    GoalieConfidence,
    InjuriesFreshness,
    LinesFeed,
)


FIXTURE = Path(__file__).parent / "fixtures" / "dailyfaceoff_combinations.json"


@pytest.fixture
def combinations() -> dict:
    """A real (trimmed) DailyFaceoff ``combinations`` payload for EDM."""
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def team(combinations):
    return DailyFaceoffClient.parse_team(combinations)


def _page_html(combinations: dict) -> str:
    """Wrap a ``combinations`` payload in a minimal __NEXT_DATA__ page."""
    payload = {"props": {"pageProps": {"combinations": combinations}}}
    return (
        '<html><body><script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(payload)}</script></body></html>"
    )


def _team_url(slug: str) -> str:
    return f"{BASE_URL}/teams/{slug}/line-combinations"


def _mock_session(router):
    """Mock a requests.Session; ``router`` maps url -> html string or Exception."""
    session = Mock(spec=requests.Session)
    session.headers = {}

    def _get(url, timeout=None):
        result = router[url]
        if isinstance(result, Exception):
            raise result
        resp = Mock()
        resp.raise_for_status = Mock()
        resp.text = result
        return resp

    session.get = Mock(side_effect=_get)
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


# --- parse_team -------------------------------------------------------------


def test_parse_team_reads_metadata(team):
    assert_that(team.team_slug, equal_to("edmonton-oilers"))
    assert_that(team.team_abbr, equal_to("EDM"))
    assert_that(team.team_name, equal_to("Edmonton Oilers"))
    assert_that(
        team.updated_at,
        equal_to(datetime(2026, 10, 23, 14, 7, 18, 977000, tzinfo=timezone.utc)),
    )


def test_parse_team_forward_lines_in_order(team):
    assert_that(team.forward_lines, has_length(4))
    first_line = [p.ascii_last for p in team.forward_lines[0]]
    assert_that(first_line, contains_exactly("podkolzin", "mcdavid", "draisaitl"))


def test_parse_team_defense_pairs_in_order_drops_empty(team):
    # The feed lists a (ratingless, empty) 4th pair; it must not appear.
    assert_that(team.defense_pairs, has_length(3))
    first_pair = [p.ascii_last for p in team.defense_pairs[0]]
    assert_that(first_pair, contains_exactly("ekholm", "bouchard"))


def test_parse_team_goalies_starter_first_and_unconfirmed(team):
    goalies = team.goalies

    assert_that(goalies, has_length(2))
    assert_that(goalies[0].goalie.ascii_last, equal_to("levi"))
    assert_that(goalies[0].is_starter, is_(True))
    assert_that(goalies[1].is_starter, is_(False))
    assert_that(goalies[0].confidence, equal_to(GoalieConfidence.UNCONFIRMED))


def test_parse_team_power_play_units_pp1_before_pp2(team):
    pp = team.power_play_units

    assert_that(pp, has_length(2))
    assert_that(pp[0][0].ascii_last, equal_to("hyman"))
    assert_that(pp[1][0].ascii_last, equal_to("podkolzin"))


def test_parse_team_penalty_kill_units_populated(team):
    # PK units are the capability the dead mirror feed never carried.
    pk = team.penalty_kill_units

    assert_that(pk, has_length(2))
    assert_that(pk[0][0].ascii_last, equal_to("mcdavid"))


def test_parse_team_injuries_from_off_ice_list(team):
    injuries = team.injuries

    assert_that(injuries, has_length(6))
    statuses = {i.player.ascii_last: i.status for i in injuries}
    assert_that(statuses["ekholm"], equal_to("dtd"))
    assert_that(statuses["regula"], equal_to("ir"))
    # The off-ice list carries no position/description.
    assert_that(injuries[0].position, is_(none()))


def test_parse_team_scratches_always_empty(team):
    # The off-ice list is injuries only; there is no healthy-scratch list.
    assert_that(team.scratches, is_(empty()))


def test_parse_team_rejects_non_dict_payload():
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient.parse_team(["not", "a", "dict"])


def test_parse_team_rejects_payload_without_players():
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient.parse_team({"teamSlug": "edmonton-oilers"})


def test_parse_team_tolerates_missing_special_teams():
    minimal = {
        "teamSlug": "boston-bruins",
        "teamAbbreviation": "BOS",
        "players": [
            {
                "name": "A B",
                "categoryIdentifier": "ev",
                "groupIdentifier": "f1",
                "positionIdentifier": "c",
            },
        ],
    }

    bos = DailyFaceoffClient.parse_team(minimal)

    assert_that(bos.forward_lines, has_length(1))
    assert_that(bos.power_play_units, is_(empty()))
    assert_that(bos.penalty_kill_units, is_(empty()))
    assert_that(bos.goalies, is_(empty()))
    assert_that(bos.injuries, is_(empty()))
    assert_that(bos.updated_at, is_(none()))


# --- _extract_combinations --------------------------------------------------


def test_extract_combinations_from_page(combinations):
    extracted = DailyFaceoffClient._extract_combinations(_page_html(combinations))

    assert_that(extracted["teamSlug"], equal_to("edmonton-oilers"))


def test_extract_combinations_raises_without_next_data():
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient._extract_combinations("<html>no data here</html>")


def test_extract_combinations_raises_on_bad_json():
    html = '<script id="__NEXT_DATA__" type="application/json">{nope}</script>'
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient._extract_combinations(html)


def test_extract_combinations_raises_when_absent():
    html = (
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props": {"pageProps": {}}}</script>'
    )
    with pytest.raises(NewsSourceUnavailableError):
        DailyFaceoffClient._extract_combinations(html)


# --- is_stale ---------------------------------------------------------------


def _feed_with(updated_at):
    return LinesFeed(source="dailyfaceoff.com", updated_at=updated_at, teams={})


def test_is_stale_false_for_recent_feed():
    client = DailyFaceoffClient(stale_after=timedelta(hours=36))
    updated = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

    assert_that(
        client.is_stale(_feed_with(updated), now=updated + timedelta(hours=1)),
        is_(False),
    )


def test_is_stale_true_past_threshold():
    client = DailyFaceoffClient(stale_after=timedelta(hours=36))
    updated = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

    assert_that(
        client.is_stale(_feed_with(updated), now=updated + timedelta(hours=48)),
        is_(True),
    )


def test_is_stale_true_when_timestamp_missing():
    client = DailyFaceoffClient()

    assert_that(client.is_stale(_feed_with(None)), is_(True))


# --- fetch_team / fetch_lines -----------------------------------------------


def test_fetch_team_returns_parsed_team(combinations):
    url = _team_url("edmonton-oilers")
    client = DailyFaceoffClient(session=_mock_session({url: _page_html(combinations)}))

    team = client.fetch_team("edmonton-oilers")

    assert_that(team.team_abbr, equal_to("EDM"))
    assert_that(team.penalty_kill_units, has_length(2))


def test_fetch_team_raises_on_network_error():
    url = _team_url("edmonton-oilers")
    client = DailyFaceoffClient(
        session=_mock_session({url: requests.ConnectionError("boom")})
    )

    with pytest.raises(NewsSourceUnavailableError):
        client.fetch_team("edmonton-oilers")


def test_fetch_lines_aggregates_teams_and_newest_timestamp(combinations):
    older = dict(
        combinations,
        teamSlug="older",
        teamAbbreviation="OLD",
        updatedAt="2026-10-20T00:00:00.000Z",
    )
    newer = dict(
        combinations, teamSlug="edmonton-oilers", updatedAt="2026-10-23T14:07:18.977Z"
    )
    router = {
        _team_url("older"): _page_html(older),
        _team_url("edmonton-oilers"): _page_html(newer),
    }
    client = DailyFaceoffClient(session=_mock_session(router))

    feed = client.fetch_lines(slugs=["older", "edmonton-oilers"])

    assert_that(len(feed.teams), equal_to(2))
    assert_that(feed.injuries_status, equal_to(InjuriesFreshness.FRESH))
    # Feed timestamp is the freshest team's.
    assert_that(
        feed.updated_at,
        equal_to(datetime(2026, 10, 23, 14, 7, 18, 977000, tzinfo=timezone.utc)),
    )


def test_fetch_lines_skips_failing_team_but_keeps_others(combinations, caplog):
    router = {
        _team_url("edmonton-oilers"): _page_html(combinations),
        _team_url("broken-team"): requests.ConnectionError("boom"),
    }
    client = DailyFaceoffClient(session=_mock_session(router))

    with caplog.at_level("WARNING"):
        feed = client.fetch_lines(slugs=["edmonton-oilers", "broken-team"])

    assert_that(list(feed.teams), contains_exactly("edmonton-oilers"))
    assert_that(caplog.text, contains_string("broken-team"))


def test_fetch_lines_raises_when_all_teams_fail():
    router = {_team_url("broken-team"): requests.ConnectionError("boom")}
    client = DailyFaceoffClient(session=_mock_session(router))

    with pytest.raises(NewsSourceUnavailableError):
        client.fetch_lines(slugs=["broken-team"])


def test_fetch_lines_warns_when_stale(combinations, caplog):
    stale = dict(combinations, updatedAt="2020-01-01T00:00:00.000Z")
    url = _team_url("edmonton-oilers")
    client = DailyFaceoffClient(session=_mock_session({url: _page_html(stale)}))

    with caplog.at_level("WARNING"):
        client.fetch_lines(slugs=["edmonton-oilers"])

    assert_that(caplog.text, contains_string("stale"))
