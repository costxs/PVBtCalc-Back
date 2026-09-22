"""Every piece of text written into an exported workbook.

The export is ALWAYS English, whatever language the interface is in, so files are
comparable across users and readable by scripts. There is deliberately no language
parameter anywhere in the export path: nothing here (or in the routes/schemas) takes
one, and adding one would defeat the purpose.

The client-side fallback writer (PVBtCalc/src/tools/exportText.ts) carries the same
text. Both are pinned to shared-fixtures/export_text.json by their test suites
(tests/test_export_text_shared.py and src/tools/exportText.test.ts), so the two
writers cannot drift apart.
"""
from typing import Optional

NOTE_HEADER = "Note"
NOT_AVAILABLE = "not available"
CHART_SUMMARY_SHEET = "Chart Summary"

# One name for the wormhole length quantity in every sheet. "L" is NOT used: it collides
# with the characteristic length L in the model's nomenclature.
WORMHOLE_LENGTH = "Wormhole Length"

SIM_HEADER = ["q0 [gal/(ft.min)]", "V_A [gal/ft]", "iv [m/s]", "wv [m/s]", "dv [m/s]", "1/Da", "tbt [s]", NOTE_HEADER]
DESIGN_HEADER = [f"{WORMHOLE_LENGTH} [ft]", "q_opt [gal/(ft.min)]", "V_opt [gal/ft]", "tbt [min]", "Temperature [°C]", NOTE_HEADER]
SKIN_HEADER = ["V_A [gal/ft]", "skin", f"{WORMHOLE_LENGTH} [ft]", NOTE_HEADER]

# Optimum Analysis (radial): swept parameter -> (label, unit). Temperature is Celsius: the
# model, T_CALIBRATED_K and every backend payload stay Kelvin internally; kelvin_to_celsius_display
# (temperature.py) converts at the boundary, applied by whoever builds the row/note values
# (export_workbook.py's _analysis_rows for Analysis rows/notes, _design_rows_for_temp for Design rows).
ANALYSIS_META = {
    "temperature": ("Temperature", "°C"),
    "porosity": ("Porosity", "fraction"),
    "acid_concentration": ("Acid Concentration", "w/w"),
    "wellbore_diameter": ("Wellbore Diameter", "in"),
    "payzone_thickness": ("Payzone Thickness", "ft"),
}


def analysis_axis(sweep_param: str) -> tuple[str, str]:
    return ANALYSIS_META.get(sweep_param, (sweep_param, ""))


def analysis_header(sweep_param: str) -> list[str]:
    label, unit = analysis_axis(sweep_param)
    return [f"{label} [{unit}]", "q_opt [gal/(ft.min)]", "V_opt [gal/ft]", "tbt [min]", NOTE_HEADER]


def join_and(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])} and {items[-1]}"


def fmt_num(x: float) -> str:
    """6 significant digits, no trailing zeros (mirrors String(Number(x.toPrecision(6))))."""
    return format(x, ".6g")


def _q_opt_suffix(q_opt_str: Optional[str]) -> str:
    return f"; q_opt = {q_opt_str} gal/(ft·min)" if q_opt_str else ""


# ---- Simulation sheet (radial)
def sim_note(is_border: bool, q_opt_str: Optional[str]) -> str:
    head = "Minimum at the edge of the simulated range" if is_border else "Minimum V_A of this simulation"
    return head + _q_opt_suffix(q_opt_str)


# ---- Design sheet naming. The sheet name and its own embedded figure legend use a bare "C"
# (no degree sign): xlsx sheet names accept "." and "°" but this keeps one look for the pair.
# The 2-decimal Celsius value is exact (no repeating decimal for any of this app's inputs),
# so it is not a lossy rounding -- see kelvin_to_celsius_display for the noise it is scrubbing.
def design_sheet_label(temperature_c: float) -> str:
    return f"{temperature_c:.2f} C"


def design_sheet_name(temperature_c: float) -> str:
    return f"Design {design_sheet_label(temperature_c)}"


def design_figure_stem(temperature_c: float) -> str:
    return f"design_{temperature_c:.2f}C"


def design_target_note(target_str: str, length_ft: float) -> str:
    return f"Target {target_str} ft ({WORMHOLE_LENGTH} = {length_ft:.2f} ft)"


def design_missed_note(target_strs: list[str], last_length_ft: float) -> str:
    label = "Target" if len(target_strs) == 1 else "Targets"
    return (f"{label} {join_and(target_strs)} ft not reached — "
            f"table ends at {last_length_ft:.2f} ft (limit 1000 gal/ft)")


# ---- Optimum Analysis sheet
# T_CALIBRATED_K is the only calibrated range in the app, and it is always the temperature
# sweep's range, so this note's unit is fixed at °C (the caller passes lo/hi already
# converted -- see export_workbook.py's _analysis_rows).
def analysis_note_outside(lo: float, hi: float) -> str:
    return f"Outside calibrated range ({lo:g}–{hi:g} °C)"


def analysis_note_skipped() -> str:
    return "No interior optimum — point omitted"


def analysis_note_clipped(x_str: str, unit: str) -> str:
    return f"Series truncated — {x_str} {unit} exceeds the 1000 gal/ft limit"


# ---- Skin sheet
def skin_note(target_skin: Optional[float]) -> str:
    if target_skin is None:
        return "Final skin"
    return f"Target skin (closest to {fmt_num(target_skin)})"


# ---- Linear workbook
def linear_note(is_border: bool, q_opt_str: Optional[str], unit: str) -> str:
    head = "Minimum at the edge of the simulated range" if is_border else "Minimum PVBT of this simulation"
    return head + (f"; q_opt = {q_opt_str} {unit}" if q_opt_str else "")
