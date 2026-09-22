"""Contrato TS<->Python do TEXTO do export (shared-fixtures/export_text.json).

O export e SEMPRE em ingles e nao tem parametro de idioma. Este teste trava o texto do
writer do servidor; src/tools/exportText.test.ts trava o mesmo texto no writer do cliente.
Tambem garante que nenhum schema/rota do export aceita idioma.

    venv/Scripts/python.exe -m pytest tests/test_export_text_shared.py
"""
import inspect
import json
import os

from app.routes import exportLinear, exportRadial
from app.schemas import LinearExportRequest, RadialExportRequest
from app.services import export_text as et

_fixture_path = os.path.join(os.path.dirname(__file__), "..", "shared-fixtures", "export_text.json")
if not os.path.exists(_fixture_path):
    _fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "shared-fixtures", "export_text.json")
FIXTURE = json.load(open(_fixture_path, encoding="utf-8"))


def test_constants_match_shared_fixture():
    c = FIXTURE["constants"]
    assert et.NOTE_HEADER == c["note_header"]
    assert et.NOT_AVAILABLE == c["not_available"]
    assert et.CHART_SUMMARY_SHEET == c["chart_summary_sheet"]
    assert et.WORMHOLE_LENGTH == c["wormhole_length"]
    assert et.SIM_HEADER == c["sim_header"]
    assert et.DESIGN_HEADER == c["design_header"]
    assert et.SKIN_HEADER == c["skin_header"]
    assert {k: list(v) for k, v in et.ANALYSIS_META.items()} == c["analysis_meta"]
    for param, header in FIXTURE["analysis_headers"].items():
        assert et.analysis_header(param) == header


def test_design_sheet_naming_matches_shared_fixture():
    for case in FIXTURE["design_sheet_naming"]:
        assert et.design_sheet_label(case["temperature_c"]) == case["label"], case
        assert et.design_sheet_name(case["temperature_c"]) == case["name"], case
        assert et.design_figure_stem(case["temperature_c"]) == case["figure_stem"], case


def test_notes_match_shared_fixture():
    for case in FIXTURE["notes"]:
        assert getattr(et, case["fn"])(*case["args"]) == case["expected"], case


def test_wormhole_length_has_one_name_and_never_bare_L():
    for header in (et.DESIGN_HEADER, et.SKIN_HEADER):
        assert any(h.startswith("Wormhole Length [ft]") for h in header)
        assert not any(h.startswith("L [") or h.startswith("comprimento") for h in header)


def test_export_text_is_english_only():
    """No Portuguese anywhere in the constants or in a rendering of every note."""
    texts = [et.NOTE_HEADER, et.NOT_AVAILABLE, et.CHART_SUMMARY_SHEET, *et.SIM_HEADER, *et.DESIGN_HEADER, *et.SKIN_HEADER]
    texts += [x for pair in et.ANALYSIS_META.values() for x in pair]
    texts += [case["expected"] for case in FIXTURE["notes"]]
    accented = [t for t in texts if any(ch in t for ch in "áàâãéêíóôõúçÁÉÍÓÚÇ")]
    assert accented == []
    for banned in ("Nota", "Alvo", "não", "comprimento", "temperatura", "Resumo"):
        assert not [t for t in texts if banned in t], banned


def test_no_export_schema_or_route_takes_a_language():
    """The export has no language parameter, on purpose (see export_text.py)."""
    def is_language_name(name: str) -> bool:
        n = name.lower()
        return n in {"lang", "language", "locale", "idioma"} or n.endswith("_lang") or n.endswith("_language")

    def all_fields(model, seen=None):
        seen = seen if seen is not None else set()
        if model in seen:
            return []
        seen.add(model)
        names = list(model.model_fields)
        for f in model.model_fields.values():
            for arg in [f.annotation, *getattr(f.annotation, "__args__", ())]:
                if hasattr(arg, "model_fields"):
                    names += all_fields(arg, seen)
        return names

    for model in (RadialExportRequest, LinearExportRequest):
        assert [n for n in all_fields(model) if is_language_name(n)] == [], model.__name__

    for mod in (exportRadial, exportLinear):
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if fn.__module__ != mod.__name__:
                continue
            params = inspect.signature(fn).parameters
            assert [p for p in params if is_language_name(p)] == [], f"{mod.__name__}.{name}"
