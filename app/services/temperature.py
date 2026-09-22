"""Boundary rule: state and every backend payload stay in Kelvin (the model is calibrated in
Kelvin -- Eq. 18 takes T in K, T_CALIBRATED_K is (283, 478)). Celsius exists only at the
display boundary (what gets written to a cell or a note) -- there is no user-input boundary on
this side, since every backend route takes temperature already converted by the frontend (see
tools/temperature.ts). celsius_to_kelvin is kept here anyway, as the exact mirror of the TS
function, in case a future caller needs it.

Both conversions are pure -- no rounding -- and kelvin_to_celsius is meant to be called
exactly once per value, at the point something is rendered or written; never on a value
already produced by kelvin_to_celsius, and never for a calibrated-range comparison -- compare
against T_CALIBRATED_K directly, in Kelvin (see radial_optimum_sweep.py's validate_sweep);
only the MESSAGE TEXT is Celsius. Round only in a display formatter (round_celsius below),
applied after kelvin_to_celsius, never inside it.
"""
KELVIN_OFFSET = 273.15


def celsius_to_kelvin(c: float) -> float:
    return c + KELVIN_OFFSET


def kelvin_to_celsius(k: float) -> float:
    return k - KELVIN_OFFSET


# Display formatter, not a conversion: kelvin_to_celsius(290) is 16.850000000000023, not 16.85
# (subtracting 273.15 in floating point leaves noise around 1e-13). Call this at a write site,
# with the SAME `decimals` as whatever it must match -- e.g. the Analysis sheet/notes use the
# same decimals as export_workbook.py's Design/Analysis row builders agree on. Never call this
# on a value used afterwards for a comparison.
def round_celsius(k: float, decimals: int) -> float:
    return round(kelvin_to_celsius(k), decimals)


# The calibrated range, in Celsius, for MESSAGE TEXT ONLY -- never for a comparison. The
# calibrated-range check (radial_optimum_sweep.py's validate_sweep) compares the Kelvin value
# against T_CALIBRATED_K directly; this constant only formats what a note says. 283/478 K
# convert to an exact two-decimal Celsius bound (no repeating digit), so rounding here loses
# nothing. Mirrors tools/temperature.ts's T_CALIBRATED_C.
from app.services.PVBTradialFunc import T_CALIBRATED_K  # noqa: E402
T_CALIBRATED_C = (round_celsius(T_CALIBRATED_K[0], 2), round_celsius(T_CALIBRATED_K[1], 2))
