import pytest

from app.services.PVBTradialFunc import T_CALIBRATED_K
from app.services.temperature import (
    KELVIN_OFFSET, T_CALIBRATED_C, celsius_to_kelvin, kelvin_to_celsius, round_celsius,
)

# The values a mistake would most plausibly hit: the calibrated bound (both directions, since
# a boundary-exact input must not be spuriously rejected), a couple of realistic user inputs,
# and 0/negative to make sure the offset sign isn't flipped.
ROUND_TRIP_VALUES = (9.85, 23.85, 24.05, 204.85, 0, -50, 1000)


def test_celsius_to_kelvin_has_no_rounding():
    assert celsius_to_kelvin(24.07) != celsius_to_kelvin(24.05)
    assert celsius_to_kelvin(24.07) == pytest.approx(297.22, abs=1e-9)


@pytest.mark.parametrize("c", ROUND_TRIP_VALUES)
def test_round_trip(c):
    assert kelvin_to_celsius(celsius_to_kelvin(c)) == pytest.approx(c, abs=1e-9)


def test_applying_kelvin_to_celsius_twice_is_not_the_identity():
    """The failure mode this guards: a value already converted in one place gets converted
    again in another -- still a plausible-looking number ("297 -> 23.85 -> -249.3"), so only
    a test catches it."""
    for k in (297.2, 400):
        once_plausible = kelvin_to_celsius(k)
        twice_wrong = kelvin_to_celsius(once_plausible)
        assert abs(twice_wrong - once_plausible) > 100


def test_celsius_to_kelvin_of_the_bound_reproduces_kelvin_bound():
    """No rounding trade-off: 283/478 K convert to an exact two-decimal Celsius bound."""
    assert celsius_to_kelvin(9.85) == pytest.approx(283, abs=1e-9)
    assert celsius_to_kelvin(204.85) == pytest.approx(478, abs=1e-9)
    assert T_CALIBRATED_C == (9.85, 204.85)
    assert tuple(T_CALIBRATED_K) == (283, 478)


def test_round_celsius_scrubs_float_noise_applied_after_the_conversion():
    assert kelvin_to_celsius(290) != 16.85  # the float noise this formatter is scrubbing
    assert round_celsius(290, 2) == 16.85
    assert round_celsius(283, 2) == 9.85
    assert round_celsius(270, 2) == -3.15
