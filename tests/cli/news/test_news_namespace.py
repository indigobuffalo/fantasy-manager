from hamcrest import assert_that, equal_to, is_in, contains_string

from fantasy_manager.cli.news import ACTIONS, News
from fantasy_manager.cli.news.lineups import Lineups


def test_lineups_is_registered():
    assert_that(ACTIONS["lineups"], equal_to(Lineups))


def test_parse_args_routes_action_and_defers_flags():
    # options_first keeps sub-action flags (e.g. --output) in <args>.
    args = News().parse_args(["news", "lineups", "--output=json", "edmonton-oilers"])
    assert_that(args["<action>"], equal_to("lineups"))
    assert_that("--output=json", is_in(args["<args>"]))
    assert_that("edmonton-oilers", is_in(args["<args>"]))


def test_run_unknown_action_is_a_clean_error():
    args = News().parse_args(["news", "bogus"])
    result = News().run(args)
    assert_that(result.return_code, equal_to(1))
    assert_that(result.message, contains_string("unknown news action 'bogus'"))
    assert_that(result.message, contains_string("lineups"))


def test_run_surfaces_subaction_usage_errors():
    # An option 'lineups' doesn't define should come back as a clean per-action
    # usage error, not an uncaught DocoptExit.
    args = News().parse_args(["news", "lineups", "--bogus"])
    result = News().run(args)
    assert_that(result.return_code, equal_to(1))
    assert_that(result.message, contains_string("news lineups"))
