from hamcrest import assert_that, equal_to, has_item, is_in

from fantasy_manager.model.enums.sport import Sport


def test_nhl_is_a_member():
    assert_that(Sport.NHL.value, equal_to("NHL"))


def test_lookup_by_value():
    assert_that(Sport("NHL"), equal_to(Sport.NHL))


def test_lookup_by_name():
    assert_that(Sport["NHL"], equal_to(Sport.NHL))


def test_nhl_is_present_in_members():
    assert_that(Sport.NHL, is_in(list(Sport)))
    assert_that([s.value for s in Sport], has_item("NHL"))
