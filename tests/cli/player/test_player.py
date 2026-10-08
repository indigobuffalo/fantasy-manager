from hamcrest import assert_that, equal_to, is_in, contains_string

from fantasy_manager.cli.player import ACTIONS, Player
from fantasy_manager.cli.player.availability import Availability


def test_availability_is_registered():
    assert_that(ACTIONS["availability"], equal_to(Availability))


def test_parse_args_routes_action_and_defers_flags():
    # options_first keeps sub-action flags (e.g. --leagues) in <args>.
    args = Player().parse_args(
        ["player", "availability", "--leagues=1,2", "McDavid"]
    )
    assert_that(args["<action>"], equal_to("availability"))
    assert_that("--leagues=1,2", is_in(args["<args>"]))
    assert_that("McDavid", is_in(args["<args>"]))


def test_run_unknown_action_is_a_clean_error():
    args = Player().parse_args(["player", "bogus"])
    result = Player().run(args)
    assert_that(result.return_code, equal_to(1))
    assert_that(result.message, contains_string("unknown player action 'bogus'"))
    assert_that(result.message, contains_string("availability"))


def test_run_surfaces_subaction_usage_errors():
    # 'availability' requires at least one <player>; a missing arg should come
    # back as a clean per-action usage error, not an uncaught DocoptExit.
    args = Player().parse_args(["player", "availability"])
    result = Player().run(args)
    assert_that(result.return_code, equal_to(1))
    assert_that(result.message, contains_string("player availability"))
