"""
tests/test_linear_optimum_shared.py

Fixture COMPARTILHADA com PVBtCalc/src/tools/linearExport.shared.test.ts
(shared-fixtures/linear_optimum_cases.json): Nota, resumo e marcador do otimo
linear. Se a regra mudar so no Python (ou so no TS), uma das duas suites falha.

    venv/Scripts/python.exe -m pytest tests/test_linear_optimum_shared.py -v
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from app.schemas import LinearModelCurve
from app.services import export_workbook_linear as ewl

FIXTURE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "shared-fixtures", "linear_optimum_cases.json"))
with open(FIXTURE, encoding="utf-8") as f:
    CASES = json.load(f)["cases"]


def test_fixture_cobre_os_casos_exigidos():
    names = {c["name"] for c in CASES}
    assert {"optimum_inside_sweep", "optimum_below_sweep", "optimum_above_sweep",
            "legacy_curve_without_pvbt_at_q_opt"} <= names


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_caso(case):
    inp, e = case["input"], case["expected"]
    curve = LinearModelCurve(id="X", flowratepoints=inp["flowratepoints"],
                             pvbtpoints=inp["pvbtpoints"], metadata=inp["metadata"])
    info = ewl.analyze_linear_curve(curve)
    assert info["min_idx"] == e["min_idx"]
    assert info["is_border"] == e["is_border"]
    assert ewl.build_note(info, info["min_idx"]) == e["note"]
    marker = ewl.optimum_marker(info, curve.flowratepoints)
    assert (None if marker is None else {"x": marker[0], "y": marker[1]}) == e["marker"]
    assert dict(ewl.build_summary_rows(info)) == e["summary"]
