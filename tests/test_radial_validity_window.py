"""
tests/test_radial_validity_window.py

Fase 2 -- a janela de validade sai de build_curves (o mesmo caminho que
routes/pvbtRadialCurve.py aciona) como arrays paralelos + metadata, em
gal/(ft.min) desde a Fase 8 (antes bbl/min -- ver units.flowrate_to_display).
Script de asserts (sem pytest), estilo do harness do modulo.

    venv/Scripts/python.exe -m tests.test_radial_validity_window
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas import RadialCurveOutput  # noqa: E402
from app.services.PVBTfunc import AcidType  # noqa: E402
from app.services.PVBTradialFunc import (  # noqa: E402
    RadialCurveMaster,
    floor_zero_flow,
    opt_search_window,
)

from app.services.units import flowrate_to_m3s, m3s_to_flowrate, BBL_TO_GAL  # noqa: E402


def _display_to_m3s(value_gal_ft_min, payzone_thickness_ft):
    """Inverso de units.flowrate_to_display, so para as asserts deste teste
    (a rota nunca precisa ir dessa unidade de volta para m3/s)."""
    value_bbl_min = value_gal_ft_min * payzone_thickness_ft / BBL_TO_GAL
    return flowrate_to_m3s(value_bbl_min, "bbl_min")

_NUMERIC_ARRAYS = (
    "flowratepoints", "pvbtpoints", "acidvolumepoints", "insterticialvelocity",
    "ida", "volumetobt", "timetobt", "wormholevelocity", "darcyvelocity",
)
_NULLABLE_AT_CLIPPED = ("pvbtpoints", "acidvolumepoints", "volumetobt", "timetobt")


def _assert_no_inf_nan(curve):
    """None e valor valido (ponto clipado). O que nao pode aparecer e float
    inf/nan -- vira Infinity/NaN no JSON e quebra o parser do front."""
    for key in _NUMERIC_ARRAYS:
        for i, v in enumerate(curve[key]):
            if v is None:
                assert key in _NULLABLE_AT_CLIPPED and curve["status"][i] == "clipped", (
                    f"{curve['target_label']}: {key}[{i}] = None sem status clipped"
                )
            else:
                assert math.isfinite(v), f"{curve['target_label']}: {key}[{i}] = {v!r}"


def _master():
    return RadialCurveMaster(
        acid_type_cls=AcidType.getAcidTypeByStr("HCl With Inhibitor Corrosion"),
        acid_concentration=0.15,
        rock_type="Indiana Limestone",
        porosity=0.30,
        temperature_k=297.20,
        wellbore_radius_in=6.0,
        payzone_thickness_ft=200.0,
        drainage_radius_ft=None,
    )


def test_validity_window_contract():
    flow_min, flow_max, steps = 0.1, 5.0, 12
    master = _master()
    curves = master.build_curves(
        target_mode="length",
        targets_display=[5.0, 20.0, 50.0],
        flow_min_m3s=flowrate_to_m3s(flow_min, "bbl_min"),
        flow_max_m3s=flowrate_to_m3s(flow_max, "bbl_min"),
        steps=steps,
    )

    RadialCurveOutput(output_mode="pvbt", curves=curves, parameters=master.get_adjusted_parameters())

    for c in curves:
        n = len(c["flowratepoints"])
        assert len(c["within_validity_range"]) == n == len(c["status"]), c["target_label"]
        assert all(isinstance(v, bool) for v in c["within_validity_range"])
        assert "metadata" in c and "within_validity_range" in c
        assert not any(isinstance(v, dict) for v in c["within_validity_range"])

        md = c["metadata"]
        assert md is not None, f"{c['target_label']}: metadata None inesperado neste caso"
        q_opt_m3s = _display_to_m3s(md["q_opt_gal_ft_min"], master.payzone_thickness_ft)
        assert abs(md["validity_min_gal_ft_min"] - md["q_opt_gal_ft_min"] / 10.0) < 1e-12
        assert abs(md["validity_max_gal_ft_min"] - md["q_opt_gal_ft_min"] * 10.0) < 1e-12

        vmin = _display_to_m3s(md["validity_min_gal_ft_min"], master.payzone_thickness_ft)
        vmax = _display_to_m3s(md["validity_max_gal_ft_min"], master.payzone_thickness_ft)
        for fr_gal, flag in zip(c["flowratepoints"], c["within_validity_range"]):
            q = _display_to_m3s(fr_gal, master.payzone_thickness_ft)
            assert flag == (vmin <= q <= vmax), (c["target_label"], fr_gal, flag)

        _assert_no_inf_nan(c)

        print(f"[{c['target_label']}] q_opt={md['q_opt_gal_ft_min']:.4f} gal/(ft.min)  "
              f"janela=[{md['validity_min_gal_ft_min']:.4f}, {md['validity_max_gal_ft_min']:.4f}]  "
              f"flags={c['within_validity_range']}")

    assert any(not all(c["within_validity_range"]) for c in curves)


def test_sweep_starting_at_zero_window():
    """flow_min = 0 e cenario real (linspace incluiria o 0 como 1o ponto).
    O MESMO piso (flow_max_m3s * 1e-9) e aplicado em dois lugares: a janela de
    busca de q_opt (opt_search_window) e o proprio sweep da curva
    (build_curves, antes do linspace) -- via floor_zero_flow."""
    fmax = flowrate_to_m3s(5.0, "bbl_min")

    assert floor_zero_flow(0.0, fmax) == fmax * 1e-9
    assert floor_zero_flow(123.0, fmax) == 123.0

    q_lo, q_hi = opt_search_window(0.0, fmax)
    assert q_lo > 0.0, "q_lo=0 quebra a busca em escala log"
    assert abs(q_lo - fmax * 1e-9) < 1e-24, (q_lo, fmax * 1e-9)

    master = _master()
    curves = master.build_curves(
        target_mode="length", targets_display=[5.0],
        flow_min_m3s=0.0, flow_max_m3s=fmax, steps=5,
    )
    RadialCurveOutput(output_mode="pvbt", curves=curves, parameters=master.get_adjusted_parameters())
    c = curves[0]
    assert c["metadata"] is not None
    assert len(c["within_validity_range"]) == len(c["flowratepoints"]) == 5

    first_gal = c["flowratepoints"][0]
    assert first_gal > 0.0, "sweep ainda comeca em q=0"
    assert abs(_display_to_m3s(first_gal, master.payzone_thickness_ft) - fmax * 1e-9) < 1e-24
    _assert_no_inf_nan(c)

    assert c["status"][0] == "clipped"
    assert c["pvbtpoints"][0] is None
    assert c["acidvolumepoints"][0] is None
    assert c["volumetobt"][0] is None
    assert c["timetobt"][0] is None
    assert c["status"][-1] == "ok"
    assert isinstance(c["timetobt"][-1], float)

    assert c["within_validity_range"][0] is False
    print(f"[sweep-from-0] 1o ponto={first_gal:.3e} gal/(ft.min) (= fmax*1e-9 em m3/s)  "
          f"status[0]={c['status'][0]}  timetobt[0]={c['timetobt'][0]}  "
          f"metadata={c['metadata']}")


if __name__ == "__main__":
    test_validity_window_contract()
    test_sweep_starting_at_zero_window()
    print("\nOK -- contrato da janela de validade verificado.")
