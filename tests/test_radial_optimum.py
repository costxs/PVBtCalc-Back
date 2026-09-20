"""
tests/test_radial_optimum.py

Fase 1 -- guarda contra a regressao dos bounds chumbados de
PVBtRadial.optimum_flowrate (antes q_lo=1e-9, q_hi=1e-2 fixos em m3/s).

Convencao do projeto: sem pytest instalado no venv; teste e script de
asserts + prints, no mesmo estilo do harness __main__ de
services/PVBTradialFunc.py. Rodar:

    venv/Scripts/python.exe -m tests.test_radial_optimum
    (ou: venv/Scripts/python.exe tests/test_radial_optimum.py)
"""
import os
import sys

import numpy as np
from scipy.optimize import minimize_scalar

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.PVBTradialFunc import (  # noqa: E402
    PVBtRadial,
    RadialGeometry,
    opt_search_window,
    target_to_lambda,
)
from app.services.units import flowrate_to_m3s  # noqa: E402

ACID = dict(a=5.10e-4, b=35.1, n=0.65, k0=2.43e6, Dm=3.24e-9, C_Ao=0.15, X=0.5417)


def _model(geo, q):
    return PVBtRadial(geo, flowrate_m3s=q, **ACID)


def _acid_volume(geo, lam, q):
    return _model(geo, q).acid_volume(lam)


def _true_optimum(geo, lam, lo=1e-10, hi=1e2, n=4000):
    """Minimo de referencia, independente de optimum_flowrate: varredura
    densa em escala log + refino local. Faixa larguissima de proposito --
    o objetivo e o minimo fisico real, nao uma borda."""
    qs = np.logspace(np.log10(lo), np.log10(hi), n)
    vals = np.array([_acid_volume(geo, lam, q) for q in qs])
    i = int(np.argmin(vals))
    a, b = qs[max(i - 1, 0)], qs[min(i + 1, n - 1)]
    r = minimize_scalar(lambda q: _acid_volume(geo, lam, q),
                        bounds=(a, b), method="bounded", options={"xatol": 1e-14})
    return r.x


def _edge_frac(q, q_lo, q_hi):
    """Distancia (fracao do vao, em decadas) de q ate a borda mais proxima.
    < 0.01 => q encostou na borda => busca cortada, nao minimo real."""
    span = np.log(q_hi / q_lo)
    return min(np.log(q / q_lo), np.log(q_hi / q)) / span


def _case(name, rw_in, h_ft, phi, target_ft, sweep_bbl_min):
    geo = RadialGeometry(r_w_m=rw_in * 0.0254, h_o_m=h_ft * 0.3048, porosity=phi)
    lam = target_to_lambda(target_ft, "length", geo.beta, geo.L)

    flow_min = flowrate_to_m3s(sweep_bbl_min[0], "bbl_min")
    flow_max = flowrate_to_m3s(sweep_bbl_min[1], "bbl_min")
    q_lo0, q_hi0 = opt_search_window(flow_min, flow_max)

    q_opt, _v, (q_lo_eff, q_hi_eff) = _model(geo, flow_max).optimum_flowrate(
        lam, q_lo0, q_hi0, return_bounds=True
    )
    q_true = _true_optimum(geo, lam)
    frac = _edge_frac(q_opt, q_lo_eff, q_hi_eff)
    rel_err = abs(q_opt - q_true) / q_true

    print(f"\n[{name}] rw={rw_in}in h={h_ft}ft phi={phi} alvo={target_ft}ft  "
          f"sweep={sweep_bbl_min} bbl/min")
    print(f"    janela inicial : [{q_lo0:.3e}, {q_hi0:.3e}] m3/s")
    print(f"    janela efetiva : [{q_lo_eff:.3e}, {q_hi_eff:.3e}] m3/s  (alargada pelo metodo)")
    print(f"    q_opt          : {q_opt:.6e} m3/s")
    print(f"    q_true (scan)  : {q_true:.6e} m3/s   erro rel = {rel_err:.2%}")
    print(f"    dist. da borda : {frac:.3f} do vao  (limite: > 0.01)")

    assert frac > 0.01, (
        f"[{name}] q_opt a {frac:.3%} da borda da janela "
        f"[{q_lo_eff:.3e}, {q_hi_eff:.3e}] -- busca cortada pela borda, nao e minimo real"
    )
    assert rel_err < 0.02, (
        f"[{name}] q_opt={q_opt:.3e} nao bate com o minimo real {q_true:.3e} "
        f"(erro {rel_err:.2%})"
    )
    return geo, lam, q_true


def test_no_edge_pinning():
    geo, lam, q_true = _case("campo/alvo-longo", 6, 200, 0.30, 50, (0.1, 5))

    def V(q):
        return _acid_volume(geo, lam, q)
    r_old = minimize_scalar(V, bounds=(1e-9, 1e-2), method="bounded",
                            options={"xatol": 1e-12})
    frac_old = _edge_frac(r_old.x, 1e-9, 1e-2)
    print(f"\n[bracket fixo antigo 1e-9..1e-2] q={r_old.x:.6e}  dist. borda={frac_old:.4f}")
    assert frac_old < 0.01, (
        "esperado: o bracket fixo antigo devolve a propria borda 1e-2 -- "
        "se este assert falhar, o teste de borda perdeu o sentido"
    )
    assert abs(r_old.x - q_true) / q_true > 0.02, (
        "esperado: bracket fixo antigo NAO acha o minimo real"
    )

    _case("core-pequeno", 1.5, 1, 0.15, 5, (0.1, 5))
    _case("campo/medio", 4, 50, 0.20, 10, (0.1, 5))


def test_widen_has_physical_ceiling():
    """O alargamento nao pode rodar pra sempre nem alargar ate uma faixa de
    vazao absurda so porque tecnicamente e interior. Analogo ao `hi > 1e8`
    de penetration_from_volume."""
    geo = RadialGeometry(r_w_m=6 * 0.0254, h_o_m=200 * 0.3048, porosity=0.30)
    lam = target_to_lambda(50.0, "length", geo.beta, geo.L)
    model = _model(geo, 1e-3)

    saved = PVBtRadial.Q_SEARCH_CEIL_M3S
    try:
        PVBtRadial.Q_SEARCH_CEIL_M3S = 3e-3
        raised = False
        try:
            model.optimum_flowrate(lam, 1e-4, 1e-3)
        except ValueError as e:
            raised = True
            msg = str(e)
        assert raised, "esperava ValueError ao bater no teto fisico, nao um q_opt na borda"
        assert "faixa fisica" in msg, msg
        print(f"\n[teto fisico] ValueError como esperado: {msg}")
    finally:
        PVBtRadial.Q_SEARCH_CEIL_M3S = saved

    from app.services.PVBTfunc import AcidType
    from app.services.PVBTradialFunc import RadialCurveMaster
    from app.services.units import flowrate_to_m3s
    m = RadialCurveMaster(AcidType.getAcidTypeByStr("HCl With Inhibitor Corrosion"),
                          0.15, "Indiana Limestone", 0.30, 24.05, 6.0, 200.0, None)
    saved = PVBtRadial.optimum_flowrate
    try:
        def _boom(self, *a, **k):
            raise ValueError("curva sem minimo interior fisico (forcado no teste)")
        PVBtRadial.optimum_flowrate = _boom
        curves = m.build_curves("length", [50.0],
                                flowrate_to_m3s(0.1, "bbl_min"),
                                flowrate_to_m3s(5.0, "bbl_min"), 6)
    finally:
        PVBtRadial.optimum_flowrate = saved
    c = curves[0]
    assert c["metadata"] is None
    assert c["within_validity_range"] == [True] * len(c["flowratepoints"])
    print("[degrade] optimum_flowrate falha -> metadata=None, within_validity_range todo True -- OK")


if __name__ == "__main__":
    test_no_edge_pinning()
    test_widen_has_physical_ceiling()
    print("\nOK -- todas as asserts passaram.")
