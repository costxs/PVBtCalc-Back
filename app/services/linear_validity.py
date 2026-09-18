"""
services/linear_validity.py

Fase 6.3 -- janela de validade da vazao para o regime LINEAR.

Arquivo NOVO, isolado, IRMAO de linear_optimum.py. NAO importa nada de
PVBTfunc.py e nao mexe em nenhuma funcao dele (em particular NAO toca
WormholeVelocityCalculator). A unica dependencia de calculo e
optimum_flowrate_linear (linear_optimum.py, Fase 6.1); units.py entra
so pra converter q_opt de m3/s para a unidade de escala de core.

Mesma logica que o Radial ja aplica em
PVBTradialFunc.RadialCurveMaster._validity_window /
_build_single_curve, aqui de forma stateless e sem AoS:

  q_opt        -> optimum_flowrate_linear(...)          [m3/s]
  validity_min -> q_opt / 10
  validity_max -> q_opt * 10
  within[i]    -> validity_min <= q[i] <= validity_max

Unidade de metadata: cm3/min. O Linear e escala de core (o front coleta
a vazao em cm3/min em InletPressure.tsx / SimuCard "Flowrate sweep"),
nao bbl/min como o Radial (escala de campo). A conversao passa por
units.m3s_to_flowrate(x, "cm3_min") -- NAO por PVBTfunc.ConvertUnits,
que e o caminho ja validado do calculo principal e nao deve ser tocado;
esta e uma conversao paralela, so pra anotacao.

Degradacao conservadora (mesmo padrao ja aprovado no Radial): se
optimum_flowrate_linear levantar -- brentq sem troca de sinal dentro do
bracket ancorado na Eq. 34, i.e. curva sem minimo interior nesse
intervalo -- devolvemos metadata=None e within_validity_range = [True]*N
(sem anotacao), nao [False]*N.
"""
from app.services.linear_optimum import optimum_flowrate_linear
from app.services.units import m3s_to_flowrate


def linear_validity_window(flowrates_cm3_min, a, b, n, keff, A_o, lc, phi, C_Ao, X):
    """
    Recebe os pontos de vazao da curva JA em cm3/min (o mesmo array que
    PVBtMaster.PVBtCurveCalculatorWhiteDetails devolve em FlowratePoints)
    e os parametros escalares do modelo linear.

    Retorna (within_validity_range, metadata):
      - within_validity_range: list[bool], paralelo a flowrates_cm3_min (SoA).
      - metadata: dict com q_opt_cm3_min / validity_min_cm3_min /
        validity_max_cm3_min, ou None na degradacao.

    A comparacao da janela e feita direto em cm3/min: e um reescalonamento
    linear de m3/s, entao min <= q <= max da o mesmo resultado em qualquer
    das duas unidades.
    """
    try:
        q_opt_m3s = optimum_flowrate_linear(a, b, n, keff, A_o, lc, phi, C_Ao, X)
    except (ValueError, RuntimeError):
        # brentq sem troca de sinal no bracket (ou falha de convergencia):
        # curva sem minimo interior fisico neste intervalo -> degrada.
        return [True] * len(flowrates_cm3_min), None

    q_opt_cm3_min = m3s_to_flowrate(q_opt_m3s, "cm3_min")
    validity_min = q_opt_cm3_min / 10.0
    validity_max = q_opt_cm3_min * 10.0

    within_validity_range = [
        bool(validity_min <= q <= validity_max) for q in flowrates_cm3_min
    ]
    metadata = {
        "q_opt_cm3_min": q_opt_cm3_min,
        "validity_min_cm3_min": validity_min,
        "validity_max_cm3_min": validity_max,
    }
    return within_validity_range, metadata
