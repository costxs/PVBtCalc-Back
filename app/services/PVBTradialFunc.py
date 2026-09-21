"""
services/PVBTradialFunc.py

Nucleo do modelo radial (Ali & Ziauddin, 2019, JPSE 106776).

Escopo do SciPy: SOMENTE aqui. O modelo linear (services/PVBTfunc.py)
continua puro NumPy, sem nenhuma mudanca -- essa e uma decisao
deliberada, nao um descuido: nao ha motivo para arriscar o
comportamento ja validado do linear so porque o radial ganhou uma
dependencia nova.

As funcoes fechadas (omega, alpha, acid_volume) permanecem NumPy puro
-- SciPy so entra onde nao ha forma fechada: inversao (achar lambda
dado um volume) e otimizacao (achar a vazao otima).
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import brentq, minimize_scalar

try:
    from app.services.units import flowrate_to_m3s, m3s_to_flowrate, flowrate_to_display
    from app.services.PVBTfunc import ROCKFLOWFRACTION
except ImportError:
    import os
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from app.services.units import flowrate_to_m3s, m3s_to_flowrate, flowrate_to_display
    from app.services.PVBTfunc import ROCKFLOWFRACTION


@dataclass(frozen=True)
class RadialGeometry:
    r_w_m: float
    h_o_m: float
    porosity: float
    L: float = 1.0

    def __post_init__(self):
        if self.r_w_m <= 0 or self.h_o_m <= 0:
            raise ValueError("r_w e h_o devem ser positivos")
        if not 0.0 < self.porosity < 1.0:
            raise ValueError("porosidade deve estar entre 0 e 1")

    @property
    def beta(self): return self.r_w_m / self.L
    @property
    def h(self): return self.h_o_m / self.L
    @property
    def A_o(self): return 2.0 * np.pi * self.r_w_m * self.h_o_m

    def area(self, lam):
        return 2.0 * self.h * np.pi * self.L**2 * (self.beta + lam)

    def pore_volume(self, lam):
        return self.porosity * np.pi * self.L**3 * self.h * ((self.beta + lam)**2 - self.beta**2)


class PVBtRadial:
    LIMITE_EXP = 700.0

    def __init__(self, geometry: RadialGeometry, a, b, n, k0, Dm,
                 C_Ao, X, flowrate_m3s, M=60.0, f=1.0):
        self.g = geometry
        self.a, self.b, self.n, self.k0 = a, b, n, k0
        self.Dm, self.C_Ao, self.X = Dm, C_Ao, X
        self.q_o = flowrate_m3s
        self.M = M
        self.f = f

    @property
    def keff(self): return self.k0 * self.Dm
    @property
    def v_o(self): return self.q_o / self.g.A_o
    @property
    def K(self):
        """Da*omega = keff*L/v_o -- CONSTANTE, nao varia com lambda mesmo
        v variando no radial. Nunca reconstitua Da*omega multiplicando um
        Da guardado por omega(lambda): o resultado sai errado sem avisar."""
        return self.g.L * self.keff / self.v_o

    def inv_omega(self, lam):
        return (self.a / self.g.A_o) * self.g.area(lam)**self.n + self.b * self.v_o

    def omega(self, lam):
        """Eq. 36."""
        return 1.0 / self.inv_omega(lam)

    def alpha(self, lam):
        """Primitiva exata de 1/omega (Eq. 38), com alpha(0)=0."""
        c = (self.a * (2.0*self.g.h*np.pi*self.g.L**2)**self.n) / (self.g.A_o*(self.n+1.0))
        return c*((self.g.beta+lam)**(self.n+1.0) - self.g.beta**(self.n+1.0)) + self.b*self.v_o*lam

    def _integral_fechada(self, lam):
        """f*(e^{K*alpha}-1)/K -- nucleo comum as Eqs. 41 e 42, ja escalado
        pela fracao de fluxo f. Ponto UNICO de aplicacao de f: acid_volume e
        tau derivam os dois daqui, entao qualquer consumidor futuro (e
        pore_volume_to_breakthrough/penetration_from_volume/optimum_flowrate,
        que ja passam por acid_volume) escala junto automaticamente. Aplicar
        f so em um dos dois quebraria a identidade acid_volume == M*q_o*tau
        (teste de regressao obrigatorio no bloco __main__ deste arquivo)."""
        K = self.K
        expoente = np.clip(K * self.alpha(lam), None, self.LIMITE_EXP)
        return self.f * np.expm1(expoente) / K

    def acid_volume(self, lam):
        """Eq. 42, forma fechada. f entra via _integral_fechada."""
        return (self.g.L * self.g.A_o) / (self.C_Ao * self.X) * self._integral_fechada(lam)

    def V_acid(self, lam, q_m3s=None):
        """Alias para acid_volume(lam). Se q_m3s for fornecido e diferente do atual, reavalia."""
        if q_m3s is not None and q_m3s != self.q_o:
            clone = PVBtRadial(self.g, self.a, self.b, self.n, self.k0,
                               self.Dm, self.C_Ao, self.X, q_m3s, self.M, self.f)
            return clone.acid_volume(lam)
        return self.acid_volume(lam)

    def tau(self, lam):
        """Eq. 41, forma fechada -- ADIMENSIONAL (tempo do artigo normalizado
        pela constante M). Consistencia: acid_volume(lam) deve ser sempre
        igual a M*q_o*tau(lam) -- teste de regressao obrigatorio. f entra via
        _integral_fechada (mesmo ponto que acid_volume), entao os dois
        continuam escalando juntos.
        NAO usar para popular a coluna "tbt (s)" -- ver time_to_breakthrough_s."""
        return self.g.L / (self.M * self.v_o * self.C_Ao * self.X) * self._integral_fechada(lam)

    def time_to_breakthrough_s(self, lam):
        """Tempo de bombeio ate o breakthrough, em SEGUNDOS: M*tau(lam), que
        por construcao (ver docstring de tau) e igual a acid_volume(lam)/q_o.
        E o numero acionavel pro engenheiro (quanto tempo bombear) -- tau
        sozinho e adimensional e nao deve ir pra tabela/export rotulado "(s)"."""
        return self.M * self.tau(lam)

    def pore_volume_to_breakthrough(self, lam):
        return self.acid_volume(lam) / self.g.pore_volume(lam)

    def penetration_from_volume(self, V_alvo, lam_max=200.0):
        if V_alvo <= 0:
            return 0.0
        f = lambda lam: self.acid_volume(lam) - V_alvo
        hi = lam_max
        while f(hi) < 0:
            hi *= 2.0
            if hi > 1e8:
                raise ValueError("penetracao fora de faixa fisica para este volume")
        return brentq(f, 0.0, hi, xtol=1e-13, rtol=1e-13)

    Q_SEARCH_FLOOR_M3S = 1e-9
    Q_SEARCH_CEIL_M3S = 1.0

    def optimum_flowrate(self, lam, q_lo, q_hi, return_bounds=False,
                         _edge_frac=0.02, _max_widen=40):
        """Vazao que minimiza acid_volume(lam). A curva V(q) e em U e nao
        tem forma fechada para o minimo.

        `q_lo`/`q_hi` sao a JANELA DE BUSCA (m3/s) e NAO tem valor default:
        o chamador deriva do sweep pedido / da geometria da run
        (ver OPT_SEARCH_SCALE / opt_search_window) -- nunca um teto absoluto
        fixo. O bug anterior era q_hi=1e-2 chumbado: em geometria de campo
        com alvo longo o minimo real fica acima disso e a busca devolvia a
        propria borda como se fosse o otimo.

        Se o minimo bater na borda, a janela e alargada daquele lado (mesma
        tatica de penetration_from_volume) ate o minimo ficar no interior.
        O alargamento tem DUAS travas: (1) limite fisico absoluto
        Q_SEARCH_FLOOR/CEIL, e (2) teto de iteracoes _max_widen. Bater em
        qualquer uma => ValueError (nao devolve borda).

        Retorna (q_opt, V_min); com return_bounds=True retorna
        (q_opt, V_min, (q_lo_efetivo, q_hi_efetivo)) -- a janela ja alargada,
        para o teste poder checar que q_opt nao encostou na borda.
        """
        if not (0.0 < q_lo < q_hi):
            raise ValueError(f"janela de busca invalida: q_lo={q_lo!r}, q_hi={q_hi!r}")

        def V(q):
            clone = PVBtRadial(self.g, self.a, self.b, self.n, self.k0,
                               self.Dm, self.C_Ao, self.X, q, self.M, self.f)
            return clone.acid_volume(lam)

        for _ in range(_max_widen):
            r = minimize_scalar(V, bounds=(q_lo, q_hi), method="bounded",
                                options={"xatol": 1e-12})
            q = r.x
            span = np.log(q_hi / q_lo)
            if np.log(q / q_lo) < _edge_frac * span:
                q_lo /= 10.0
            elif np.log(q_hi / q) < _edge_frac * span:
                q_hi *= 10.0
            else:
                return (q, r.fun, (q_lo, q_hi)) if return_bounds else (q, r.fun)

            if q_lo < self.Q_SEARCH_FLOOR_M3S or q_hi > self.Q_SEARCH_CEIL_M3S:
                raise ValueError(
                    "optimum_flowrate: minimo continua na borda ao alargar a "
                    f"janela ate [{q_lo:.3e}, {q_hi:.3e}] m3/s, fora da faixa "
                    f"fisica [{self.Q_SEARCH_FLOOR_M3S:.0e}, {self.Q_SEARCH_CEIL_M3S:.0e}] "
                    "-- curva sem minimo interior fisico para este alvo"
                )
        raise ValueError(
            f"optimum_flowrate: minimo nao saiu da borda em {_max_widen} "
            f"alargamentos (janela [{q_lo:.3e}, {q_hi:.3e}] m3/s)"
        )


FT_TO_M = 0.3048
IN_TO_M = 0.0254

OPT_SEARCH_SCALE = 10.0

SWEEP_FLOOR_FRAC = 1e-9


def floor_zero_flow(flow_min_m3s, flow_max_m3s):
    """flow_min_m3s como esta, exceto 0 -> flow_max_m3s * SWEEP_FLOOR_FRAC."""
    return flow_min_m3s if flow_min_m3s > 0.0 else flow_max_m3s * SWEEP_FLOOR_FRAC


def opt_search_window(flow_min_m3s, flow_max_m3s, scale=OPT_SEARCH_SCALE):
    """Janela inicial [q_lo, q_hi] (m3/s) para PVBtRadial.optimum_flowrate,
    derivada do sweep pedido. q_lo nunca vai a zero mesmo se flow_min for 0."""
    q_hi = flow_max_m3s * scale
    q_lo = max(floor_zero_flow(flow_min_m3s, flow_max_m3s), q_hi * 1e-9) / scale
    return q_lo, q_hi


# Faixa de temperatura (K) em que as correlacoes do modelo radial foram calibradas.
# UNICA definicao: schemas.py (RadialSystem, SkinEvolutionInput), o sweep do
# Optimum Analysis e (espelhado em TS) SimuCard.tsx/sweepValidation.ts usam isto.
T_CALIBRATED_K = (283.0, 478.0)


def diffusion_coefficient(temperature_k, acid_concentration):
    """Mesma formula de services/PVBTfunc.py:PVBtSetup.SetDifusionCoeficient,
    duplicada aqui (nao importada) para manter o radial desacoplado do
    arquivo linear -- ver nota de escopo no topo do modulo."""
    return np.exp((-2270.0 / temperature_k) + 1.326 * acid_concentration - 12.11)


def acid_density(acid_concentration, temperature_c):
    """Mesma formula de services/PVBTfunc.py:PVBtSetup.SetAcidDensity,
    duplicada aqui pelo mesmo motivo do resto do modulo. Unidade: g/cm3."""
    return (
        1.00683961828436
        + 0.00507208224518196 * acid_concentration * 100
        - 0.00050572878832986 * temperature_c
    )


def acid_volumetric_dissolving_power100(acid_concentration, temperature_c):
    """Mesma cadeia densidade->poder de dissolucao de PVBTfunc.py:PVBtSetup
    (Set*DissolvingPower*), duplicada aqui pelo mesmo motivo acima."""
    vm, MWm, va, MWa = 1, 100.1, 2, 36.5
    gravimetric = acid_concentration * ((vm * MWm) / (va * MWa))
    roa = acid_density(acid_concentration, temperature_c) * 62.428
    rom = 169.0
    volumetric = gravimetric * (roa / rom)
    return volumetric / acid_concentration


def target_to_lambda(target, target_mode, beta, L=1.0):
    """Inverso exato de lambdaToFt/lambdaToSkin no frontend
    (src/redux/radial/targetConversion.ts) -- precisa ficar em sincronia
    com aquelas formulas."""
    if target_mode == "length":
        return (target * FT_TO_M) / L
    if target_mode == "skin":
        return beta * (np.exp(-target) - 1.0)
    raise ValueError(f"target_mode desconhecido: {target_mode!r}")


class RadialCurveMaster:
    """Orquestra PVBtRadial para o endpoint /pvbtradialcurve. As vazoes ja
    chegam em m3/s (a rota converte de bbl/min via app.services.units); aqui
    so convertemos a geometria (polegadas, pes, Celsius) para SI e varremos
    vazao x alvo de penetracao. A SAIDA (flowratepoints/metadata de
    build_curves) volta em gal/(ft.min) via units.flowrate_to_display --
    Fase 8: o artigo normaliza por pe de zona, bbl/min cru nao e comparavel
    entre pocos de espessura diferente."""

    def __init__(
        self,
        acid_type_cls,
        acid_concentration,
        rock_type,
        porosity,
        temperature_k,
        wellbore_radius_in,
        payzone_thickness_ft,
        drainage_radius_ft=None,
    ):
        self.acidsetup = acid_type_cls(acid_concentration)
        self.acid_concentration = acid_concentration
        self.rock_type = rock_type
        self.payzone_thickness_ft = payzone_thickness_ft
        self.drainage_radius_ft = drainage_radius_ft
        self.geometry = RadialGeometry(
            r_w_m=wellbore_radius_in * IN_TO_M,
            h_o_m=payzone_thickness_ft * FT_TO_M,
            porosity=porosity,
        )
        self.temperature_k = temperature_k
        self.Dm = diffusion_coefficient(temperature_k, acid_concentration)
        self.X = acid_volumetric_dissolving_power100(acid_concentration, temperature_k - 273.15)
        self.acid_density = acid_density(acid_concentration, temperature_k - 273.15)
        self.f = ROCKFLOWFRACTION.get(rock_type, 1.0)

    @property
    def output_mode(self) -> str:
        """"pvbt" quando ha raio de drenagem informado -- so ai PVBt tem um
        volume poroso de referencia e o numero fecha um significado. Sem ele,
        "volume": a saida util e o volume de acido (gal/ft), e o frontend
        (columnsConfig.buildSimulationTable) omite a coluna PVBt e ranqueia o
        otimo por V_A.

        Ate a Fase 9 a rota devolvia "pvbt" chumbado: esse ramo "volume" nunca
        executou, apesar de o frontend e a mensagem da UI ("no drainage radius
        set -- acid volume instead of PVBt") ja o anunciarem.

        drainage_radius_ft None, 0 ou negativo => "volume" (0 nao e raio valido).
        """
        return "pvbt" if (self.drainage_radius_ft or 0) > 0 else "volume"

    def get_adjusted_parameters(self):
        """Bloco de parametros efetivamente resolvidos (AcidSetup + densidade
        + poder de dissolucao) para este request -- espelha tools.py:getparam
        do modelo linear. Existe para o painel "Adjusted Parameters" do
        frontend poder confirmar visualmente qual classe de acido o backend
        carregou (ver nota de escopo em RadialCurveOutput.parameters)."""
        return {
            "ro": self.acid_density,
            "X": self.X,
            "x": self.X * self.acid_concentration,
            "n": self.acidsetup.n,
            "a": self.acidsetup.a,
            "b": self.acidsetup.b,
            "k0": self.acidsetup.k0,
            "f": self.f,
        }

    def build_curves(self, target_mode, targets_display, flow_min_m3s, flow_max_m3s, steps):
        flow_start = floor_zero_flow(flow_min_m3s, flow_max_m3s)
        flow_points = np.linspace(flow_start, flow_max_m3s, steps)
        return [
            self._build_single_curve(target, target_mode, flow_points,
                                     flow_min_m3s, flow_max_m3s)
            for target in targets_display
        ]

    def _model_at(self, q):
        return PVBtRadial(
            self.geometry,
            a=self.acidsetup.a, b=self.acidsetup.b, n=self.acidsetup.n,
            k0=self.acidsetup.k0, Dm=self.Dm, C_Ao=self.acid_concentration,
            X=self.X, flowrate_m3s=q, f=self.f,
        )

    def _validity_window(self, lam, flow_min_m3s, flow_max_m3s):
        """(q_opt, validity_min, validity_max) em m3/s para este alvo, ou
        None se optimum_flowrate nao achar minimo interior. A janela de
        busca vem do sweep pedido (opt_search_window); a janela de validade
        e q_opt/10 .. q_opt*10 (Fase 2, item 4)."""
        q_lo, q_hi = opt_search_window(flow_min_m3s, flow_max_m3s)
        try:
            q_opt, _v = self._model_at(flow_max_m3s).optimum_flowrate(lam, q_lo, q_hi)
        except ValueError:
            return None
        return q_opt, q_opt / 10.0, q_opt * 10.0

    def _build_single_curve(self, target, target_mode, flow_points_m3s,
                            flow_min_m3s, flow_max_m3s):
        lam = target_to_lambda(target, target_mode, self.geometry.beta, self.geometry.L)

        window = self._validity_window(lam, flow_min_m3s, flow_max_m3s)

        flowratepoints, pvbtpoints, acidvolumepoints = [], [], []
        insterticialvelocity, ida, volumetobt, timetobt = [], [], [], []
        wormholevelocity, darcyvelocity, status, within_validity_range = [], [], [], []

        for q in flow_points_m3s:
            model = PVBtRadial(
                self.geometry,
                a=self.acidsetup.a,
                b=self.acidsetup.b,
                n=self.acidsetup.n,
                k0=self.acidsetup.k0,
                Dm=self.Dm,
                C_Ao=self.acid_concentration,
                X=self.X,
                flowrate_m3s=q,
                f=self.f,
            )

            wv = model.v_o * model.omega(0.0)

            expoente = model.K * model.alpha(lam)
            is_clipped = expoente > PVBtRadial.LIMITE_EXP

            M3_TO_GAL = 264.172
            acid_volume_gal_ft = None if is_clipped else (model.acid_volume(lam) * M3_TO_GAL) / self.payzone_thickness_ft

            flowratepoints.append(flowrate_to_display(m3s_to_flowrate(q, "bbl_min"), self.payzone_thickness_ft))
            pvbtpoints.append(None if is_clipped else model.pore_volume_to_breakthrough(lam))
            acidvolumepoints.append(acid_volume_gal_ft)
            insterticialvelocity.append(model.v_o / self.geometry.porosity)
            ida.append(model.omega(lam) / model.K)
            volumetobt.append(acid_volume_gal_ft)
            timetobt.append(None if is_clipped else model.time_to_breakthrough_s(lam))
            wormholevelocity.append(wv)
            darcyvelocity.append(model.v_o)
            status.append("clipped" if is_clipped else "ok")

            if window is None:
                within_validity_range.append(True)
            else:
                _q_opt, v_min, v_max = window
                within_validity_range.append(bool(v_min <= q <= v_max))

        if window is None:
            metadata = None
        else:
            q_opt, v_min, v_max = window
            metadata = {
                "q_opt_gal_ft_min": flowrate_to_display(m3s_to_flowrate(q_opt, "bbl_min"), self.payzone_thickness_ft),
                "validity_min_gal_ft_min": flowrate_to_display(m3s_to_flowrate(v_min, "bbl_min"), self.payzone_thickness_ft),
                "validity_max_gal_ft_min": flowrate_to_display(m3s_to_flowrate(v_max, "bbl_min"), self.payzone_thickness_ft),
            }

        label = f"{target:.2f} ft" if target_mode == "length" else f"skin {target:.2f}"
        return {
            "target": target,
            "target_label": label,
            "flowratepoints": flowratepoints,
            "pvbtpoints": pvbtpoints,
            "acidvolumepoints": acidvolumepoints,
            "insterticialvelocity": insterticialvelocity,
            "ida": ida,
            "volumetobt": volumetobt,
            "timetobt": timetobt,
            "wormholevelocity": wormholevelocity,
            "darcyvelocity": darcyvelocity,
            "status": status,
            "within_validity_range": within_validity_range,
            "metadata": metadata,
        }

    def generate_design_plot(self, temperatures_k, flow_min_m3s, flow_max_m3s, target_mode, targets, steps=20):
        if not targets:
            max_lam = target_to_lambda(20.0, "length", self.geometry.beta, self.geometry.L)
        else:
            max_lam = max(target_to_lambda(t, target_mode, self.geometry.beta, self.geometry.L) for t in targets)
            
        max_length_ft = (max_lam * self.geometry.L) / FT_TO_M
        
        steps_calculados = max(steps, int(np.ceil(max_length_ft * 4)))
        
        start_ft = 1.0 if max_length_ft >= 1.0 else max_length_ft * 0.1
        comprimentos_ft = np.linspace(start_ft, max_length_ft, steps_calculados)
        M3_TO_GAL = 264.172

        series_results = []

        q_lo, q_hi = opt_search_window(flow_min_m3s, flow_max_m3s)
        has_clipped_volume = False

        for t_k in temperatures_k:
            curva_rate = []
            curva_volume = []
            
            current_Dm = diffusion_coefficient(t_k, self.acid_concentration)
            current_X = acid_volumetric_dissolving_power100(self.acid_concentration, t_k - 273.15)
            
            model = PVBtRadial(
                self.geometry,
                a=self.acidsetup.a, b=self.acidsetup.b, n=self.acidsetup.n,
                k0=self.acidsetup.k0, Dm=current_Dm, C_Ao=self.acid_concentration,
                X=current_X, flowrate_m3s=1e-5, f=self.f
            )

            for l_ft in comprimentos_ft:
                lam = (l_ft * FT_TO_M) / self.geometry.L
                
                try:
                    q_opt, v_opt = model.optimum_flowrate(lam, q_lo, q_hi)
                    
                    q_opt_gal_min = q_opt * M3_TO_GAL * 60.0
                    q_opt_norm = q_opt_gal_min / self.payzone_thickness_ft
                    
                    v_opt_gal = v_opt * M3_TO_GAL
                    v_opt_norm = v_opt_gal / self.payzone_thickness_ft

                    if v_opt_norm > 1000.0:
                        has_clipped_volume = True
                        break
                    
                    curva_rate.append([q_opt_norm, l_ft])
                    curva_volume.append([v_opt_norm, l_ft])
                except ValueError:
                    continue

            series_results.append({
                "temperature_k": t_k,
                "optimum_rate_series": curva_rate,
                "optimum_volume_series": curva_volume
            })

        return {
            "series": series_results,
            "has_clipped_volume": has_clipped_volume
        }


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("error", RuntimeWarning)

    geo = RadialGeometry(r_w_m=0.0762, h_o_m=0.3048, porosity=0.15)
    m = PVBtRadial(geo, a=5.10e-4, b=35.1, n=0.65, k0=2.43e6,
                   Dm=3.24e-9, C_Ao=0.15, X=0.5417, flowrate_m3s=1e-5)

    print("--- fixtures de regressao ---")
    lam = 2.0
    V = m.acid_volume(lam)
    print(f"acid_volume(2.0)              = {V:.10e}")
    print(f"penetration_from_volume(V)    = {m.penetration_from_volume(V):.12f}  (esperado 2.0)")
    assert abs(m.penetration_from_volume(V) - 2.0) < 1e-9

    razao = V / (m.M * m.q_o * m.tau(lam))
    print(f"V_A / (M*q_o*tau)             = {razao:.12f}  (esperado 1.0)")
    assert abs(razao - 1.0) < 1e-9

    razao_tbt = (V / m.q_o) / m.time_to_breakthrough_s(lam)
    print(f"(V_A/q_o) / time_to_breakthrough_s = {razao_tbt:.12f}  (esperado 1.0)")
    assert abs(razao_tbt - 1.0) < 1e-9

    for s in (0.0, 1.0, 3.0):
        print(f"K constante em lam={s}: {m.K:.6f}")
    print(f"K (caso ref q_o=1e-5 m3/s)   = {m.K:.6f}  (esperado ~114.895)")
    assert abs(m.K - 114.895) < 0.01

    q_lo0, q_hi0 = m.q_o * 1e-3, m.q_o * 1e3
    q_opt, V_min = m.optimum_flowrate(lam, q_lo0, q_hi0)
    print(f"optimum_flowrate              : q={q_opt:.6e}  V={V_min:.6e}")

    geo_field = RadialGeometry(r_w_m=0.1, h_o_m=10.0, porosity=0.15)
    q_field = flowrate_to_m3s(0.5, "bbl_min")
    m_field = PVBtRadial(geo_field, a=5.10e-4, b=35.1, n=0.65, k0=2.43e6,
                         Dm=3.24e-9, C_Ao=0.15, X=0.5417, flowrate_m3s=q_field)
    print(f"K (0.5 bbl/min, geom. campo)  = {m_field.K:.6f}")
    assert 10.0 < m_field.K < 1e4, (
        f"K={m_field.K:.3e} fora da faixa fisica -- provavel bug de unidade de vazao "
        f"(ver app/services/units.py e routes/pvbtRadialCurve.py)"
    )
    assert m_field.K * m_field.alpha(lam) < PVBtRadial.LIMITE_EXP, "expoente clipando em vazao normal"
    assert abs(m3s_to_flowrate(q_field, "bbl_min") - 0.5) < 1e-12

    print("\nsem RuntimeWarning ate aqui -- overflow guard funcionando.")
    print("todas as asserts passaram.")
