"""
tests/test_radial_appendix_a_temperature.py

Fixture NUMERICO da conversao de temperatura no caminho radial.

Motivo de existir: "nao travou e nao deu NaN" NAO distingue conversao
certa de errada. Se a dupla conversao (T + 273.15 sobrando, ou o
`- 273.15` do RadialCurveMaster aplicado duas vezes) voltasse a qualquer
caminho, `acid_volume` devolveria um numero -- plausivel ou absurdo, mas
nunca uma excecao. So um valor de referencia pega isso.

Caso: Apendice A radial, entrada 297.20 K, lambda = 2, q = 1e-5 m3/s.

    V_A esperado = 7.746136919479e-02 m3

NAO usar 7.7678156513e-02: esse e o V_A com Dm=3.24e-9 e X=0.5417
(constantes ja ARREDONDADAS do paper, usadas no bloco __main__ de
PVBTradialFunc.py como ancora da algebra pura). Alimentando 297.20 K nas
formulas empiricas de verdade sai Dm=3.235591e-9 e X=0.542370, e o
exp(K*alpha) do modelo amplifica esses ~0.13% de diferenca de entrada
para ~0.28% no volume -> 7.746e-02, nao 7.768e-02.

    venv/Scripts/python.exe -m tests.test_radial_appendix_a_temperature

ARMADILHA IRMA (achada 2026-09-11, fixture da leitura guiada do Design
Plot, PVBtCalc/src/tools/designPlotReader.test.ts): um fixture proposto
para T=338.71 K usou X=0.5417 (o valor do Apendice A, tabelado a
24.05 C) em vez de recalcular pela formula empirica na temperatura real
do caso. X depende da densidade do acido, que cai com a temperatura --
em 338.71 K (65.56 C) o X correto e 0.531736, 1.87% menor que 0.5417.
Isso bastou pra estourar a tolerancia de 0.5% do fixture (a` 15 gal/ft,
o erro virou ~0.9% em l e q_opt em vez do 0.19% esperado da propria
interpolacao log-log).

Mesma familia de erro do sentinela `f=1.0` acima (ROCKFLOWFRACTION):
um parametro que E constante NUM ponto do artigo (Apendice A, 24.05 C)
mas parece generico e acaba congelado em qualquer fixture novo. Regra:
X e Dm NUNCA sao constantes de fixture -- recalcular sempre por
diffusion_coefficient()/acid_volumetric_dissolving_power100() na
temperatura do caso, mesmo quando o fixture e calculado por fora do
backend.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.PVBTradialFunc import (  # noqa: E402
    PVBtRadial,
    RadialGeometry,
    RadialCurveMaster,
    diffusion_coefficient,
    acid_volumetric_dissolving_power100,
)
from app.services.PVBTfunc import AcidType  # noqa: E402

# V_A de referencia: caminho da temperatura com as formulas empiricas
# puras avaliadas em 297.20 K (ver docstring do modulo).
EXPECTED_VA = 7.746136919479e-02
LAM = 2.0
Q_M3S = 1e-5
CONC = 0.15
TEMP_K = 297.20  # o que a UI/API manda: ja em Kelvin

# geometria do Apendice A radial (identica ao __main__ de PVBTradialFunc):
# r_w = 3 in = 0.0762 m ; h_o = 1 ft = 0.3048 m ; phi = 0.15
GEO_KWARGS = dict(r_w_m=0.0762, h_o_m=0.3048, porosity=0.15)
WELLBORE_RADIUS_IN = 0.0762 / 0.0254   # = 3.0
PAYZONE_THICKNESS_FT = 0.3048 / 0.3048  # = 1.0
ACID_SYSTEM = "HCl With Inhibitor Corrosion"


def _va_manual(temp_k: float) -> float:
    """PVBtRadial montado a mao -- Dm e X derivados de temp_k pelas
    formulas de PVBTradialFunc. Exercita as formulas de conversao."""
    acidsetup = AcidType.getAcidTypeByStr(ACID_SYSTEM)(CONC)
    geo = RadialGeometry(**GEO_KWARGS)
    Dm = diffusion_coefficient(temp_k, CONC)
    X = acid_volumetric_dissolving_power100(CONC, temp_k - 273.15)
    m = PVBtRadial(
        geo, a=acidsetup.a, b=acidsetup.b, n=acidsetup.n, k0=acidsetup.k0,
        Dm=Dm, C_Ao=CONC, X=X, flowrate_m3s=Q_M3S,
    )
    return m.acid_volume(LAM)


def _va_production(temp_k: float) -> float:
    """Caminho de PRODUCAO: RadialCurveMaster.__init__ faz a conversao
    (self.Dm = diffusion_coefficient(temperature_k, ...);
     self.X  = acid_volumetric_dissolving_power100(..., temperature_k - 273.15)).
    E a linha exata que a rota /pvbtradialcurve roda. Se o `- 273.15`
    dali fosse duplicado, so este caminho pegaria."""
    master = RadialCurveMaster(
        acid_type_cls=AcidType.getAcidTypeByStr(ACID_SYSTEM),
        acid_concentration=CONC,
        rock_type="__sentinel_no_rock__",   # fora de ROCKFLOWFRACTION -> f = 1.0
        porosity=GEO_KWARGS["porosity"],
        temperature_k=temp_k,
        wellbore_radius_in=WELLBORE_RADIUS_IN,
        payzone_thickness_ft=PAYZONE_THICKNESS_FT,
        drainage_radius_ft=None,
    )
    assert master.f == 1.0, f"f={master.f} != 1.0 -- rock_type sentinela entrou em ROCKFLOWFRACTION?"
    return master._model_at(Q_M3S).acid_volume(LAM)


def _rel(v):
    return abs(v - EXPECTED_VA) / EXPECTED_VA


def test_temperature_conversion_manual_path():
    v = _va_manual(TEMP_K)
    print(f"\n[manual]     V_A(297.20 K) = {v:.12e}   erro rel = {_rel(v):.2e}")
    assert _rel(v) < 1e-8, f"V_A={v:.12e}, esperado {EXPECTED_VA:.12e}"


def test_temperature_conversion_production_path():
    """RadialCurveMaster.__init__ -- a conversao que a rota realmente usa."""
    v = _va_production(TEMP_K)
    print(f"[production]  V_A(297.20 K) = {v:.12e}   erro rel = {_rel(v):.2e}")
    assert _rel(v) < 1e-8, (
        f"RadialCurveMaster deu V_A={v:.12e}, esperado {EXPECTED_VA:.12e} -- "
        f"conversao de temperatura no __init__ mudou?"
    )


def test_rounded_paper_constants_are_a_different_number():
    """Guarda a distincao: com Dm/X arredondados do paper o V_A e outro
    (7.7678156513e-02). Se algum dia alguem 'corrigir' EXPECTED_VA para
    esse valor, este teste explica por que nao."""
    geo = RadialGeometry(**GEO_KWARGS)
    m = PVBtRadial(geo, a=5.10e-4, b=35.1, n=0.65, k0=2.43e6,
                   Dm=3.24e-9, C_Ao=CONC, X=0.5417, flowrate_m3s=Q_M3S)
    v_rounded = m.acid_volume(LAM)
    print(f"[rounded]     V_A(Dm=3.24e-9, X=0.5417) = {v_rounded:.12e}")
    assert abs(v_rounded - 7.7678156513e-02) / 7.7678156513e-02 < 1e-9
    # e e mensuravelmente diferente do valor pelas formulas puras
    assert abs(v_rounded - EXPECTED_VA) / EXPECTED_VA > 1e-3


def test_double_conversion_is_caught_manual():
    """Reintroduz o '+ 273.15' sobrando no caminho manual."""
    v_bad = _va_manual(TEMP_K + 273.15)
    print(f"\n[poison manual]     T+273.15 -> V_A = {v_bad:.6e}  (nao travou, nao deu NaN)")
    assert _rel(v_bad) > 1000, (
        f"fixture sem dente: T+273.15 deu V_A={v_bad:.6e}, "
        f"desvio rel {_rel(v_bad):.2e} -- deveria ser >> 1000"
    )


def test_double_conversion_is_caught_production():
    """Reintroduz o '+ 273.15' sobrando no caminho de producao
    (RadialCurveMaster recebendo temperature_k ja somado)."""
    v_bad = _va_production(TEMP_K + 273.15)
    print(f"[poison production]  T+273.15 -> V_A = {v_bad:.6e}  (nao travou, nao deu NaN)")
    assert _rel(v_bad) > 1000, (
        f"fixture sem dente no caminho de producao: V_A={v_bad:.6e}, "
        f"desvio rel {_rel(v_bad):.2e}"
    )


if __name__ == "__main__":
    test_temperature_conversion_manual_path()
    test_temperature_conversion_production_path()
    test_rounded_paper_constants_are_a_different_number()
    test_double_conversion_is_caught_manual()
    test_double_conversion_is_caught_production()
    print("\nOK -- V_A(297.20 K) = 7.746136919479e-02 nos dois caminhos; "
          "dupla conversao pega nos dois.")
