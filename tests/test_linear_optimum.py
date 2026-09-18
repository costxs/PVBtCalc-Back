"""
tests/test_linear_optimum.py

Fase 6.3 -- q_opt do regime linear (linear_optimum.py) e a janela de
validade que sai de linear_validity.linear_validity_window.

Convencao do projeto: sem pytest no venv; teste e script de asserts +
prints, mesmo estilo de tests/test_radial_optimum.py e do harness
__main__ dos modulos de servico. Rodar:

    venv/Scripts/python.exe -m tests.test_linear_optimum
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.linear_optimum import optimum_flowrate_linear  # noqa: E402
from app.services.linear_validity import linear_validity_window  # noqa: E402


def _apendice_a_params():
    """Mesmo caso do Apendice A ja validado -- identico ao bloco __main__ de
    services/linear_optimum.py (HCl com inibidor, core de 1.5 in x 6 in)."""
    n, a, b, k0 = 0.65, 5.10e-4, 35.1, 2.43e6
    r_c = (1.5 / 2) * 0.0254
    A_o = np.pi * r_c**2
    lc = 6 * 0.0254
    C_Ao, X, phi = 0.15, 0.5417, 0.15
    T_K = 297.2
    Dm = np.exp(-2270.0 / T_K + 1.326 * C_Ao - 12.11)
    keff = k0 * Dm
    return dict(a=a, b=b, n=n, keff=keff, A_o=A_o, lc=lc, phi=phi, C_Ao=C_Ao, X=X)


def test_apendice_a_q_opt():
    p = _apendice_a_params()
    q_opt_m3s = optimum_flowrate_linear(**p)
    q_opt_cm3_min = q_opt_m3s * 1e6 * 60
    print(f"[apendice A] q_opt = {q_opt_cm3_min:.4f} cm3/min  (esperado 1.7054)")
    assert abs(q_opt_cm3_min - 1.7054) < 1e-3, q_opt_cm3_min


def test_validity_window_contract():
    p = _apendice_a_params()
    # sweep sintetico em cm3/min, com pontos dentro E fora da janela
    # (q_opt ~1.7054 => janela ~[0.1705, 17.054])
    flowrates = [0.05, 0.20, 1.7054, 5.0, 30.0]
    within, metadata = linear_validity_window(flowrates, **p)

    assert metadata is not None
    assert len(within) == len(flowrates)
    assert all(isinstance(v, bool) for v in within)
    # nao virou objeto-por-ponto (SoA, nao AoS)
    assert not any(isinstance(v, dict) for v in within)

    # metadata em cm3/min (nao m3/s cru: q_opt seria ~2.8e-8 se fosse m3/s)
    assert abs(metadata["q_opt_cm3_min"] - 1.7054) < 1e-3, metadata
    # janela = q_opt/10 .. q_opt*10
    assert abs(metadata["validity_min_cm3_min"] - metadata["q_opt_cm3_min"] / 10.0) < 1e-12
    assert abs(metadata["validity_max_cm3_min"] - metadata["q_opt_cm3_min"] * 10.0) < 1e-12

    lo, hi = metadata["validity_min_cm3_min"], metadata["validity_max_cm3_min"]
    for q, flag in zip(flowrates, within):
        assert flag == (lo <= q <= hi), (q, flag)
    # exercita os dois lados da janela
    assert within[0] is False and within[-1] is False
    assert any(within)
    print(f"[janela] q_opt={metadata['q_opt_cm3_min']:.4f}  "
          f"[{lo:.4f}, {hi:.4f}] cm3/min  flags={within}")


def test_degradacao_bracket_sem_raiz():
    """Caso sintetico forcando a degradacao: lc ~0 achata a Eq. 33, que
    deixa de trocar de sinal dentro do bracket ancorado na Eq. 34 ->
    brentq levanta ValueError -> linear_validity_window degrada
    (metadata=None, within_validity_range todo True). Mesmo padrao de
    degradacao conservadora ja aprovado no Radial
    (test_radial_optimum.test_widen_has_physical_ceiling)."""
    p = _apendice_a_params()
    p["lc"] = 1e-12

    # 1. a causa raiz e mesmo brentq sem raiz no bracket
    raised = False
    try:
        optimum_flowrate_linear(**p)
    except ValueError:
        raised = True
    assert raised, "esperava ValueError de brentq (bracket da Eq. 34 sem raiz da Eq. 33)"

    # 2. o consumidor degrada em vez de propagar a excecao
    flowrates = [0.05, 0.5, 5.0]
    within, metadata = linear_validity_window(flowrates, **p)
    assert metadata is None
    assert within == [True, True, True]
    print("[degrade] brentq falha -> metadata=None, within_validity_range todo True -- OK")


if __name__ == "__main__":
    test_apendice_a_q_opt()
    test_validity_window_contract()
    test_degradacao_bracket_sem_raiz()
    print("\nOK -- q_opt linear e contrato da janela de validade verificados.")
