"""
tests/test_radial_analysis_table_shared.py

Fixture COMPARTILHADA com PVBtCalc/src/tools/analysisTable.test.ts
(shared-fixtures/radial_analysis_table_cases.json): linhas e Nota da tabela do
Optimum Analysis radial. Se a regra mudar so no Python (ou so no TS), uma das
duas suites falha. Tambem checa que a aba chega ao workbook do servidor.

    venv/Scripts/python.exe -m tests.test_radial_analysis_table_shared
"""
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas import RadialAnalysisSeries, RadialExportRequest  # noqa: E402
from app.services import export_workbook as ew  # noqa: E402

FIXTURE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "shared-fixtures", "radial_analysis_table_cases.json"))
with open(FIXTURE, encoding="utf-8") as f:
    CASES = json.load(f)["cases"]


def test_rows_and_nota_match_shared_fixture():
    for c in CASES:
        rows = ew._analysis_rows(RadialAnalysisSeries(**c["input"]))
        got = [{"x": r["x"], "q_opt": r["q_opt"], "v_opt": r["v_opt"], "tbt_min": r["tbt_min"], "nota": r["nota"]}
               for r in rows]
        assert got == c["expected"], (c["name"], got)


def test_workbook_contains_analysis_sheet():
    req = RadialExportRequest(
        inputs={}, curves=[],
        analysis=RadialAnalysisSeries(**CASES[-1]["input"]),
    )
    xlsx = ew.build_workbook(req, include_images=False)
    z = zipfile.ZipFile(io.BytesIO(xlsx))
    wb_xml = z.read("xl/workbook.xml").decode("utf-8")
    assert "Analysis Temperature" in wb_xml, wb_xml
    shared = z.read("xl/sharedStrings.xml").decode("utf-8")
    assert "No interior optimum" in shared and "Series truncated" in shared
    assert "tbt [min]" in shared


def test_workbook_without_analysis_has_no_analysis_sheet():
    xlsx = ew.build_workbook(RadialExportRequest(inputs={}, curves=[]), include_images=False)
    assert "Analysis" not in zipfile.ZipFile(io.BytesIO(xlsx)).read("xl/workbook.xml").decode("utf-8")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("ALL OK")
