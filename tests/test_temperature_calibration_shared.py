"""
tests/test_temperature_calibration_shared.py

Fixture COMPARTILHADA com PVBtCalc/src/tools/sweepValidation.test.ts
(shared-fixtures/temperature_calibration.json). Se T_CALIBRATED_K mudar so no
Python (ou so em sweepValidation.ts), uma das duas suites falha. Cobre tambem
a politica do Design Plot para temperatures_to_compare (aceita e sinaliza).

    venv/Scripts/python.exe -m tests.test_temperature_calibration_shared
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pydantic import ValidationError  # noqa: E402

from app.routes.designPlot import generate_design_plot  # noqa: E402
from app.schemas import DesignPlotInput, SkinEvolutionInput  # noqa: E402
from app.services.PVBTradialFunc import T_CALIBRATED_K  # noqa: E402

FIXTURE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "shared-fixtures", "temperature_calibration.json"))
with open(FIXTURE, encoding="utf-8") as f:
    FIXTURE_RANGE = tuple(json.load(f)["t_calibrated_k"])


def _payload(temps):
    return dict(
        system=dict(rock_type="Indiana Limestone", porosity=0.15, acid_system="HCl",
                    acid_concentration=0.15, temperature_k=297.2),
        geometry=dict(wellbore_radius_in=1.5, payzone_thickness_ft=1.0),
        radial_targets=dict(target_mode="length", targets=[5.0]),
        flowrate_sweep=dict(min=0.5, max=10.0, steps=10),
        temperatures_to_compare=temps,
    )


def test_python_constant_matches_shared_fixture():
    assert tuple(T_CALIBRATED_K) == FIXTURE_RANGE, (T_CALIBRATED_K, FIXTURE_RANGE)


def test_schemas_use_the_constant():
    lo, hi = T_CALIBRATED_K
    for bad in (lo - 1.0, hi + 1.0):
        try:
            SkinEvolutionInput(acid_type="HCl", acid_concentration=0.15, temperature_k=bad,
                               core_porosity=0.15, wellbore_radius_in=1.5, payzone_thickness_ft=1.0,
                               rock_type="Indiana Limestone", flowrates_to_compare=[1.0])
        except ValidationError:
            continue
        raise AssertionError("base temperature fora da faixa deveria ser rejeitada")


def test_design_plot_flags_out_of_range_temperatures():
    out = generate_design_plot(DesignPlotInput(**_payload([270.0, 297.2, 500.0])))
    assert out["outside_calibrated_range"] == [270.0, 500.0], out["outside_calibrated_range"]
    assert {s["temperature_k"] for s in out["series"]} == {270.0, 297.2, 500.0}, "pontos continuam sendo devolvidos"
    assert generate_design_plot(DesignPlotInput(**_payload([290.0, 300.0])))["outside_calibrated_range"] == []


def test_design_plot_rejects_non_positive_temperature():
    for t in (0.0, -10.0):
        try:
            DesignPlotInput(**_payload([297.2, t]))
        except ValidationError:
            continue
        raise AssertionError(f"{t} K deveria ser rejeitado")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
