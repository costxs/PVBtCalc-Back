"""
services/linear_optimum.py

Arquivo NOVO, isolado. NAO importa nada de PVBTfunc.py, e PVBTfunc.py
nao precisa importar nada daqui a nao ser na rota que quiser expor
q_opt. Zero linha alterada no arquivo existente.

Unico ponto que usa SciPy: a chamada a brentq, no fim de optimum_flowrate.
Eq. 33 e Eq. 34 sao algebra pura -- mesma classe de funcao que ja existe
em PVBTfunc.py, calculada aqui de novo por serem pequenas e proprias
deste calculo especifico (nao duplicam o PVBt(q) inteiro, so os termos
que a derivada precisa).
"""
import numpy as np
from scipy.optimize import brentq  # UNICO import novo do modulo


def _velocidade_no_wormhole(q_o, a, n, b, A_o):
    """Eq. 29 -- velocidade no wormhole na face de injecao.

    DIVIDA TECNICA REGISTRADA (nao resolver aqui, ver nota de escopo):
    esta formula ja existe DUAS vezes no backend, nenhuma delas isolada
    como funcao pura reutilizavel:
      1. PVBTfunc.py, PVBt.WormholeVelocityCalculator() (linhas 210-218)
         -- metodo de instancia acoplado a self.darcy_velocity e ao
         pipeline inteiro de PVBt.__init__. Nao da pra importar sem
         instanciar PVBt(PVBtSetup(...)) inteiro.
      2. PVBTradialFunc.py, PVBtRadial.inv_omega()/omega() (linhas 78-83,
         rotulada "Eq. 36") -- generalizacao radial; em lam=0 colapsa
         exatamente nesta mesma forma linear.

    Extracao recomendada quando alguem for mexer nas tres: uma funcao
    pura em app/services/formulas.py (wormhole_velocity(darcy_velocity,
    a, n, b, A_o)), consumida pelas tres. NAO fazer essa extracao como
    parte da Fase 6 -- WormholeVelocityCalculator esta acoplado a uma
    classe stateful grande, e mexer nela e refatoracao com escopo/teste
    proprios, separada da feature de janela de validade que este modulo
    existe para viabilizar."""
    v_o = q_o / A_o
    return v_o / ((a / A_o) * A_o**n + b * v_o)


def _closed_form_estimate_eq34(a, b, n, keff, A_o, lc):
    """Eq. 34 -- aproximacao fechada do artigo. NumPy puro, sem iteracao."""
    aq = a * A_o**n * keff * lc
    bq = -np.exp(-1 - b * keff * lc)
    return aq * (1 + 1.3*bq - 2.6*bq**2) / (1 + 2.7*bq)


def _dPVBT_dq_eq33(q_o, a, b, n, keff, A_o, lc, phi, C_Ao, X):
    """Eq. 33 -- a derivada exata. NumPy puro, sem iteracao."""
    v = _velocidade_no_wormhole(q_o, a, n, b, A_o)
    expo = np.exp(keff * lc / v)
    termo1 = expo - 1
    termo2 = (a * A_o**n * keff * lc / q_o) * expo
    return (1 - phi) / (A_o * lc * phi * C_Ao * X * keff) * (termo1 - termo2)


def optimum_flowrate_linear(a, b, n, keff, A_o, lc, phi, C_Ao, X):
    """
    Unica funcao publica deste modulo. Acha q_opt resolvendo Eq. 33 = 0
    por brentq, com o bracket ancorado na Eq. 34 (erra o valor final em
    ~20% para o caso do Apendice A, mas acerta a vizinhanca o bastante
    para garantir troca de sinal dentro do bracket).
    """
    q_eq34 = _closed_form_estimate_eq34(a, b, n, keff, A_o, lc)
    lo, hi = q_eq34 * 0.3, q_eq34 * 3.0

    def f(q):
        return _dPVBT_dq_eq33(q, a, b, n, keff, A_o, lc, phi, C_Ao, X)

    return brentq(f, lo, hi, xtol=1e-16)


if __name__ == "__main__":
    # mesmo caso do Apendice A, ja validado nesta conversa
    n, a, b, k0 = 0.65, 5.10e-4, 35.1, 2.43e6
    r_c = (1.5/2)*0.0254
    A_o = np.pi*r_c**2
    lc = 6*0.0254
    C_Ao, X, phi = 0.15, 0.5417, 0.15
    T_K = 297.2
    Dm = np.exp(-2270.0/T_K + 1.326*C_Ao - 12.11)
    keff = k0*Dm

    q_opt = optimum_flowrate_linear(a, b, n, keff, A_o, lc, phi, C_Ao, X)
    print(f"q_opt = {q_opt*1e6*60:.4f} cm3/min  (esperado: 1.7054)")
