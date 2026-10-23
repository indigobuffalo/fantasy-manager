from datetime import datetime, timezone

import pytest
from hamcrest import (
    assert_that,
    equal_to,
    contains_string,
    has_entries,
    not_,
    has_key,
)

import fantasy_manager.cli.news.lineups as lineups_module
from fantasy_manager.cli.news.lineups import (
    SCHEMA_VERSION,
    Lineups,
    build_payload,
    resolve_slugs,
    resolve_workers,
)
from fantasy_manager.client.news.dailyfaceoff import TEAM_SLUGS
from fantasy_manager.config.config import FantasyConfig
from fantasy_manager.exceptions import InputError, NewsSourceUnavailableError
from fantasy_manager.model.lines import GoalieSlot, LinesFeed, TeamLines
from fantasy_manager.model.player import PlayerName
from fantasy_manager.util.output import OutputFormat


def _name(full: str) -> PlayerName:
    return PlayerName(full=full)


def _feed_with_oilers() -> LinesFeed:
    """A one-team feed (edmonton-oilers) with a little of every unit."""
    updated = datetime(2026, 10, 23, 14, 7, tzinfo=timezone.utc)
    team = TeamLines(
        team_slug="edmonton-oilers",
        team_abbr="EDM",
        team_name="Edmonton Oilers",
        updated_at=updated,
        forward_lines=[[_name("Connor McDavid"), _name("Leon Draisaitl")]],
        defense_pairs=[[_name("Mattias Ekholm")]],
        goalies=[GoalieSlot(goalie=_name("Stuart Skinner"), is_starter=True)],
        power_play_units=[[_name("Connor McDavid")]],
        penalty_kill_units=[[_name("Mattias Ekholm")]],
    )
    return LinesFeed(source="dailyfaceoff.com", updated_at=updated, teams={"edmonton-oilers": team})


# --- resolve_slugs ---------------------------------------------------------


def test_resolve_slugs_uses_named_teams_stripped():
    assert_that(
        resolve_slugs([" edmonton-oilers ", "boston-bruins"]),
        equal_to(["edmonton-oilers", "boston-bruins"]),
    )


def test_resolve_slugs_defaults_to_all_teams_when_empty():
    assert_that(resolve_slugs([]), equal_to(list(TEAM_SLUGS)))
    # blank-only entries collapse to the all-teams default too
    assert_that(resolve_slugs(["  "]), equal_to(list(TEAM_SLUGS)))


# --- resolve_workers -------------------------------------------------------


def test_resolve_workers_falls_back_to_configured_default():
    assert_that(
        resolve_workers(None), equal_to(int(FantasyConfig.DEFAULT_LINEUPS_WORKERS))
    )


def test_resolve_workers_parses_explicit_value():
    assert_that(resolve_workers("3"), equal_to(3))


def test_resolve_workers_rejects_non_numeric():
    with pytest.raises(InputError):
        resolve_workers("abc")


def test_resolve_workers_rejects_non_positive():
    with pytest.raises(InputError):
        resolve_workers("0")


# --- build_payload ---------------------------------------------------------


def test_build_payload_shape_and_order():
    feed = _feed_with_oilers()
    # Request two teams; only the first parsed — the second must still appear.
    payload = build_payload(feed, ["edmonton-oilers", "boston-bruins"], stale=False)

    assert_that(payload["version"], equal_to(SCHEMA_VERSION))
    assert_that(payload["source"], equal_to("dailyfaceoff.com"))
    assert_that(payload["stale"], equal_to(False))
    # Teams come back in requested order, each flagged readable.
    slugs = [team["slug"] for team in payload["teams"]]
    assert_that(slugs, equal_to(["edmonton-oilers", "boston-bruins"]))
    assert_that(payload["teams"][0]["readable"], equal_to(True))
    assert_that(payload["teams"][1], equal_to({"slug": "boston-bruins", "readable": False}))


def test_build_payload_is_json_native():
    # model_dump(mode="json") must coerce datetimes/enums to primitives so the
    # shared serialize() (plain json.dumps) never chokes.
    feed = _feed_with_oilers()
    payload = build_payload(feed, ["edmonton-oilers"], stale=True)
    assert_that(payload["stale"], equal_to(True))
    assert_that(isinstance(payload["updated_at"], str), equal_to(True))
    oilers = payload["teams"][0]
    # slug is the canonical key; the model's team_slug is dropped to avoid a dup.
    assert_that(oilers, has_entries(slug="edmonton-oilers", team_abbr="EDM"))
    assert_that(oilers, not_(has_key("team_slug")))
    goalie = oilers["goalies"][0]
    assert_that(goalie["goalie"]["full"], equal_to("Stuart Skinner"))
    assert_that(isinstance(goalie["confidence"], str), equal_to(True))


# --- run() end-to-end (client stubbed; no network) -------------------------


def test_run_success_builds_payload(monkeypatch):
    monkeypatch.setattr(
        lineups_module.DailyFaceoffClient,
        "fetch_lines",
        lambda self, slugs=None: _feed_with_oilers(),
    )
    result = Lineups().run(
        {"<team>": ["edmonton-oilers"], "--workers": None, "--output": "json"}
    )
    assert_that(result.return_code, equal_to(0))
    assert_that(result.output_format, equal_to(OutputFormat.JSON))
    assert_that(result.data["teams"][0]["slug"], equal_to("edmonton-oilers"))
    assert_that(result.message, contains_string("1/1 team"))


def test_run_total_failure_is_structured_error(monkeypatch):
    def _boom(self, slugs=None):
        raise NewsSourceUnavailableError("dailyfaceoff.com", "no teams could be fetched")

    monkeypatch.setattr(lineups_module.DailyFaceoffClient, "fetch_lines", _boom)
    result = Lineups().run(
        {"<team>": ["edmonton-oilers"], "--workers": None, "--output": "json"}
    )
    assert_that(result.return_code, equal_to(1))
    assert_that(result.data["error"]["type"], equal_to("NewsSourceUnavailableError"))
    assert_that(result.data["version"], equal_to(SCHEMA_VERSION))


def test_run_bad_workers_is_structured_error():
    result = Lineups().run(
        {"<team>": ["edmonton-oilers"], "--workers": "0", "--output": "json"}
    )
    assert_that(result.return_code, equal_to(1))
    assert_that(result.data["error"]["type"], equal_to("InputError"))
