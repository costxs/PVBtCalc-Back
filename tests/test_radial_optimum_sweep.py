"""
tests/test_radial_optimum_sweep.py

Optimum Analysis radial (services/radial_optimum_sweep.py). Estilo do projeto:
script de asserts. Rodar:

    venv/Scripts/python.exe -m tests.test_radial_optimum_sweep
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import radial_optimum_sweep as ros  # noqa: E402
from app.services.PVBTfunc import AcidType  # noqa: E402
from app.services.PVBTradialFunc import PVBtRadial, RadialCurveMaster  # noqa: E402
from app.services.units import flowrate_to_m3s  # noqa: E402

HCL = AcidType.getAcidTypeByStr("HCl")
BASE = dict(
    steps=6, target_mode="length", target=5.0, acid_type_cls=HCL,
    acid_concentration=0.15, rock_type="Indiana Limestone", porosity=0.15,
    temperature_k=297.2, wellbore_radius_in=1.5, payzone_thickness_ft=1.0,
    flow_min_m3s=flowrate_to_m3s(0.5, "bbl_min"), flow_max_m3s=flowrate_to_m3s(10.0, "bbl_min"),
)


def test_thickness_follows_analytic_power_law():
    """q_opt(h)/q_opt(h_ref) == V_opt(h)/V_opt(h_ref) == (h/h_ref)**(n-1).

    A_o ~ h entra na velocidade de wormhole via (a/A_o)*A(lam)^n; com q/h fixo
    sobra h^(n-1). Como q_opt e V_opt escalam com o MESMO expoente, V_opt/q_opt
    (tempo ate breakthrough no otimo) nao depende da espessura."""
    n = HCL(BASE["acid_concentration"]).n
    h_ref = 1.0
    hs = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
    res = {}
    for h in hs:
        o = ros.radial_optimum_sweep(sweep_param="payzone_thickness", minimum=h, maximum=h * 1.0001,
                                     **{**BASE, "steps": 2})
        assert o["optimum_rate"], f"sem ponto para h={h}"
        res[h] = (o["optimum_rate"][0], o["optimum_volume"][0])
    q0, v0 = res[h_ref]
    print(f"n={n}  h   pred=(h/h_ref)^(n-1)   q ratio    V ratio    (V/q)/(V/q)_ref")
    for h in hs:
        pred = (h / h_ref) ** (n - 1.0)
        qr, vr = res[h][0] / q0, res[h][1] / v0
        tr = (res[h][1] / res[h][0]) / (v0 / q0)
        print(f"      {h:5.1f}  {pred:.6f}          {qr:.6f}   {vr:.6f}   {tr:.6f}")
        assert abs(qr - pred) <= 1e-5 * pred, (h, qr, pred)
        assert abs(vr - pred) <= 1e-5 * pred, (h, vr, pred)
        assert abs(tr - 1.0) <= 1e-5, (h, tr)
    print("ok thickness power law")


def test_temperature_outside_calibration_is_flagged():
    from app.services.PVBTradialFunc import T_CALIBRATED_K
    o = ros.radial_optimum_sweep(sweep_param="temperature", minimum=270.0, maximum=300.0, **{**BASE, "steps": 4})
    assert o["outside_calibrated_range"], "270 K deveria ser sinalizado"
    assert all(t < T_CALIBRATED_K[0] for t in o["outside_calibrated_range"])
    assert len(o["sweep_values"]) == len(o["optimum_rate"]), "pontos continuam sendo devolvidos"
    inside = ros.radial_optimum_sweep(sweep_param="temperature", minimum=290.0, maximum=300.0, **{**BASE, "steps": 4})
    assert inside["outside_calibrated_range"] == []
    print("ok calibration flag")


def test_temperature_matches_design_plot_and_q_opt_rises():
    temps = np.linspace(290.0, 330.0, 6)
    out = ros.radial_optimum_sweep(sweep_param="temperature", minimum=290.0, maximum=330.0, **BASE)
    q, v = out["optimum_rate"], out["optimum_volume"]
    assert len(q) == 6 and all(np.diff(q) > 0), f"q_opt deve crescer com T: {q}"

    b = BASE
    master = RadialCurveMaster(
        acid_type_cls=HCL, acid_concentration=b["acid_concentration"], rock_type=b["rock_type"],
        porosity=b["porosity"], temperature_k=b["temperature_k"],
        wellbore_radius_in=b["wellbore_radius_in"], payzone_thickness_ft=b["payzone_thickness_ft"],
    )
    design = master.generate_design_plot(
        temperatures_k=list(temps), flow_min_m3s=b["flow_min_m3s"], flow_max_m3s=b["flow_max_m3s"],
        target_mode="length", targets=[b["target"]],
    )
    for i, s in enumerate(design["series"]):
        q_d, l_ft = s["optimum_rate_series"][-1]
        v_d = s["optimum_volume_series"][-1][0]
        assert abs(l_ft - b["target"]) < 1e-9
        assert abs(q[i] - q_d) <= 1e-6 * q_d, (temps[i], q[i], q_d)
        assert abs(v[i] - v_d) <= 1e-6 * v_d, (temps[i], v[i], v_d)
    print("ok temperature: agrees with Design Plot at", b["target"], "ft")


def test_min_ge_max_rejected_before_any_calculation():
    def boom(*a, **k):
        raise AssertionError("calculo executado apesar de min >= max")

    orig_opt, orig_master = PVBtRadial.optimum_flowrate, ros.RadialCurveMaster
    PVBtRadial.optimum_flowrate = boom
    ros.RadialCurveMaster = boom
    try:
        for lo, hi in ((6.0, 3.0), (5.0, 5.0)):
            try:
                ros.radial_optimum_sweep(sweep_param="wellbore_diameter", minimum=lo, maximum=hi, **BASE)
            except ValueError as e:
                assert str(e).startswith("minimum:"), e
            else:
                raise AssertionError("min >= max nao foi rejeitado")
    finally:
        PVBtRadial.optimum_flowrate, ros.RadialCurveMaster = orig_opt, orig_master
    print("ok min>=max rejected")


def test_physical_ranges_rejected():
    cases = [("porosity", 0.0, 0.3), ("porosity", 0.1, 1.0), ("acid_concentration", -0.1, 0.2),
             ("acid_concentration", 0.1, 1.5), ("temperature", 0.0, 300.0), ("temperature", -5.0, 300.0),
             ("wellbore_diameter", 0.0, 6.0), ("wellbore_diameter", -1.0, 6.0)]
    for p, lo, hi in cases:
        try:
            ros.validate_sweep(p, lo, hi, 10)
        except ValueError:
            continue
        raise AssertionError(f"{p} [{lo},{hi}] deveria ser rejeitado")
    ros.validate_sweep("porosity", 0.05, 0.3, 10)
    print("ok physical ranges")


def test_schema_rejects_bad_range_and_unknown_param():
    from pydantic import ValidationError
    from app.schemas import RadialOptimumSweepInput
    payload = dict(sweep_param="wellbore_diameter", minimum=6, maximum=3, steps=10, target=5.0,
                   acid_system="HCl", acid_concentration=0.15, rock_type="Indiana Limestone",
                   porosity=0.15, temperature_k=297.2, wellbore_radius_in=1.5, payzone_thickness_ft=1.0,
                   flow_min_bbl_min=0.5, flow_max_bbl_min=10)
    for bad in (payload, {**payload, "minimum": 3, "maximum": 6, "sweep_param": "core_length"}):
        try:
            RadialOptimumSweepInput(**bad)
        except ValidationError:
            continue
        raise AssertionError("schema deveria rejeitar")
    RadialOptimumSweepInput(**{**payload, "minimum": 3, "maximum": 6})
    print("ok schema")


def test_volume_ceiling_clips_like_design_plot():
    out = ros.radial_optimum_sweep(sweep_param="temperature", minimum=290.0, maximum=380.0,
                                   **{**BASE, "steps": 10})
    assert out["has_clipped_volume"], "T ate 380 K a 5 ft deveria estourar 1000 gal/ft"
    assert 0 < len(out["optimum_volume"]) < 10, "serie deve ser truncada, nao vazia nem completa"
    assert all(v <= 1000.0 for v in out["optimum_volume"])
    print("ok clipping: kept", len(out["optimum_volume"]), "of", BASE["steps"], "points")


KNOWN_PREMISE_FAILURES = {"test_thickness_is_a_perfect_noop"}


if __name__ == "__main__":
    failed = []
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
            except AssertionError as e:
                failed.append(name)
                print(f"FAIL {name}: {e}")
    print("ALL OK" if not failed else f"FAILED: {failed}")
    sys.exit(1 if failed else 0)
