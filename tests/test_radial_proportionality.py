"""
tests/test_radial_proportionality.py

Teste de proporcionalidade para fluxo radial e linear com diferentes litologias:
Compara Indiana Limestone (f = 1.00) e Edwards White (f = 0.52), tudo o mais identico.

Verifica:
  1. q_opt IDENTICO nos dois (f cancela na derivada)
  2. V_A de Edwards White = exatamente 0.52 x o de Indiana
  3. t_bt de Edwards White = exatamente 0.52 x o de Indiana (prova que f entrou no lugar certo)
  4. Consistencia entre todas as 4 abas:
     - Simulation Chart (/pvbtradialcurve)
     - Skin Evolution (/skinevolution)
     - Design Plot (/designplot)
     - Analysis (/pvbtanalitical)
"""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.PVBTradialFunc import (
    RadialCurveMaster,
    PVBtRadial,
    RadialGeometry,
    FT_TO_M,
    IN_TO_M,
)
from app.services.PVBTfunc import AcidType, ROCKFLOWFRACTION, PVBtMaster
from app.services.tools import generate_skin_evolution, get_correct_param
from app.schemas import SkinEvolutionInput, AnalicalInput


def test_rockflowfraction_values():
    assert ROCKFLOWFRACTION.get("Indiana Limestone") == 1.0
    assert ROCKFLOWFRACTION.get("Edwards White") == 0.52


def test_radial_core_proportionality():
    """Testa diretamente o nucleo do modelo radial (PVBtRadial)."""
    geo = RadialGeometry(r_w_m=3.0 * IN_TO_M, h_o_m=20.0 * FT_TO_M, porosity=0.15)
    acid_kwargs = dict(
        a=5.10e-4, b=35.1, n=0.65, k0=2.43e6, Dm=3.24e-9, C_Ao=0.15, X=0.5417
    )
    
    lam = (5.0 * FT_TO_M) / geo.L
    q_lo, q_hi = 1e-5, 0.1

    m_ind = PVBtRadial(geo, flowrate_m3s=1e-4, f=1.00, **acid_kwargs)
    m_edw = PVBtRadial(geo, flowrate_m3s=1e-4, f=0.52, **acid_kwargs)

    # 1. q_opt identico
    q_opt_ind, v_opt_ind = m_ind.optimum_flowrate(lam, q_lo, q_hi)
    q_opt_edw, v_opt_edw = m_edw.optimum_flowrate(lam, q_lo, q_hi)
    
    assert np.isclose(q_opt_ind, q_opt_edw, rtol=1e-5), "q_opt deve ser identico (f cancela na derivada)"

    # 2. V_A exatamente 0.52x
    assert np.isclose(v_opt_edw / v_opt_ind, 0.52, rtol=1e-5), "V_A deve escalar exatamente por 0.52"

    # 3. t_bt exatamente 0.52x
    m_opt_ind = PVBtRadial(geo, flowrate_m3s=q_opt_ind, f=1.00, **acid_kwargs)
    m_opt_edw = PVBtRadial(geo, flowrate_m3s=q_opt_edw, f=0.52, **acid_kwargs)
    tbt_ind = m_opt_ind.time_to_breakthrough_s(lam)
    tbt_edw = m_opt_edw.time_to_breakthrough_s(lam)
    assert np.isclose(tbt_edw / tbt_ind, 0.52, rtol=1e-5), "t_bt deve escalar exatamente por 0.52"


def test_simulation_curves_proportionality():
    """Aba 1: Simulation Chart (RadialCurveMaster.build_curves)."""
    params = dict(
        acid_type_cls=AcidType.getAcidTypeByStr("HCl"),
        acid_concentration=0.15,
        porosity=0.15,
        temperature_k=297.0,
        wellbore_radius_in=6.0,
        payzone_thickness_ft=20.0,
        drainage_radius_ft=100.0,
    )
    master_ind = RadialCurveMaster(rock_type="Indiana Limestone", **params)
    master_edw = RadialCurveMaster(rock_type="Edwards White", **params)

    assert master_ind.f == 1.00
    assert master_edw.f == 0.52

    curves_ind = master_ind.build_curves("length", [5.0, 10.0], 1e-5, 0.1, 10)
    curves_edw = master_edw.build_curves("length", [5.0, 10.0], 1e-5, 0.1, 10)

    for ci, ce in zip(curves_ind, curves_edw):
        # q_opt
        assert np.isclose(
            ci["metadata"]["q_opt_gal_ft_min"],
            ce["metadata"]["q_opt_gal_ft_min"],
            rtol=1e-5
        )
        # V_A sweep
        v_ind = [x for x in ci["acidvolumepoints"] if x is not None]
        v_edw = [x for x in ce["acidvolumepoints"] if x is not None]
        for vi, ve in zip(v_ind, v_edw):
            assert np.isclose(ve / vi, 0.52, rtol=1e-5)
        # t_bt sweep
        t_ind = [x for x in ci["timetobt"] if x is not None]
        t_edw = [x for x in ce["timetobt"] if x is not None]
        for ti, te in zip(t_ind, t_edw):
            assert np.isclose(te / ti, 0.52, rtol=1e-5)


def test_skin_evolution_proportionality():
    """Aba 2: Skin Evolution (generate_skin_evolution)."""
    input_ind = SkinEvolutionInput(
        acid_type="HCl",
        acid_concentration=0.15,
        temperature_k=297.0,
        core_porosity=0.15,
        wellbore_radius_in=6.0,
        payzone_thickness_ft=20.0,
        rock_type="Indiana Limestone",
        flowrates_to_compare=[0.5, 1.2, 3.0],
    )
    input_edw = input_ind.model_copy(update={"rock_type": "Edwards White"})

    res_ind = generate_skin_evolution(input_ind, [0.5, 1.2, 3.0])
    res_edw = generate_skin_evolution(input_edw, [0.5, 1.2, 3.0])

    for q in ["0.5", "1.2", "3.0"]:
        pts_i = res_ind[q]
        pts_e = res_edw[q]
        for pi, pe in zip(pts_i, pts_e):
            assert np.isclose(pe["y"], pi["y"], atol=1e-7), "Skin deve ser identico"
            if pi["x"] is not None and pe["x"] is not None and pi["x"] > 0:
                assert np.isclose(pe["x"] / pi["x"], 0.52, rtol=1e-5), "Volume deve ser 0.52x"


def test_design_plot_proportionality():
    """Aba 3: Design Plot (RadialCurveMaster.generate_design_plot)."""
    params = dict(
        acid_type_cls=AcidType.getAcidTypeByStr("HCl"),
        acid_concentration=0.15,
        porosity=0.15,
        temperature_k=297.0,
        wellbore_radius_in=6.0,
        payzone_thickness_ft=20.0,
        drainage_radius_ft=100.0,
    )
    master_ind = RadialCurveMaster(rock_type="Indiana Limestone", **params)
    master_edw = RadialCurveMaster(rock_type="Edwards White", **params)

    dp_ind = master_ind.generate_design_plot([297.0, 338.0], 1e-5, 0.1, max_length_ft=15.0, steps=10)
    dp_edw = master_edw.generate_design_plot([297.0, 338.0], 1e-5, 0.1, max_length_ft=15.0, steps=10)

    for si, se in zip(dp_ind["series"], dp_edw["series"]):
        rates_i = [p[0] for p in si["optimum_rate_series"]]
        rates_e = [p[0] for p in se["optimum_rate_series"]]
        vols_i = [p[0] for p in si["optimum_volume_series"]]
        vols_e = [p[0] for p in se["optimum_volume_series"]]

        for ri, re in zip(rates_i, rates_e):
            assert np.isclose(ri, re, rtol=1e-4), "Optimum rate no design plot deve ser identico"
        for vi, ve in zip(vols_i, vols_e):
            assert np.isclose(ve / vi, 0.52, rtol=1e-5), "Optimum volume no design plot deve ser 0.52x"


def test_optimum_analysis_proportionality():
    """Aba 4: Optimum Analysis (get_correct_param)."""
    anal_ind = AnalicalInput(
        acid_type="HCl",
        acid_concentration=0.15,
        core_diameter=1.5,
        core_length=6.0,
        core_porosity=0.15,
        rock_type="Indiana Limestone",
        temperature=297.0,
        flowrate=1.0,
        flow_regime="radial",
        wellbore_radius_in=6.0,
        payzone_thickness_ft=20.0,
        analitical_param="temperature",
        minimum_analitical=280.0,
        step_numbers=10,
        target=5.0,
        target_mode="length"
    )
    anal_edw = anal_ind.model_copy(update={"rock_type": "Edwards White"})

    res_ind = get_correct_param(anal_ind)
    res_edw = get_correct_param(anal_edw)

    v_ind = [x for x in res_ind["volumetobt"] if x is not None]
    v_edw = [x for x in res_edw["volumetobt"] if x is not None]
    for vi, ve in zip(v_ind, v_edw):
        assert np.isclose(ve / vi, 0.52, rtol=1e-5), "Analysis volume deve ser 0.52x"

    t_ind = [x for x in res_ind["timetobt"] if x is not None]
    t_edw = [x for x in res_edw["timetobt"] if x is not None]
    for ti, te in zip(t_ind, t_edw):
        assert np.isclose(te / ti, 0.52, rtol=1e-5), "Analysis timetobt deve ser 0.52x"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
