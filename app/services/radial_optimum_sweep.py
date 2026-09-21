"""
services/radial_optimum_sweep.py

Optimum Analysis do regime RADIAL. Diferente do linear (PVBt a vazao fixa),
aqui, para cada valor do parametro varrido, resolve-se o OTIMO
(vazao que minimiza o volume de acido) para um comprimento-alvo de wormhole
fixo. Saida: q_opt [gal/(ft.min)] e V_opt [gal/ft] -- mesma normalizacao por pe
e mesma regra de corte (1000 gal/ft) do Design Plot
(RadialCurveMaster.generate_design_plot).

Espessura E oferecida: q_opt e V_opt (por pe) escalam exatamente como
(h/h_ref)^(n-1), pois A_o ~ h entra na velocidade de wormhole (a/A_o)*A^n.
A razao V_opt/q_opt (tempo ate breakthrough) e independente de h.
Temperatura fora de T_CALIBRATED_K NAO e rejeitada (so <= 0 K e); os pontos
voltam em outside_calibrated_range para o frontend avisar.
"""
import numpy as np

from app.services.PVBTradialFunc import (
    FT_TO_M,
    IN_TO_M,
    PVBtRadial,
    RadialCurveMaster,
    T_CALIBRATED_K,
    opt_search_window,
    target_to_lambda,
)

M3_TO_GAL = 264.172
VOLUME_CEILING_GAL_FT = 1000.0

# parametro -> (rotulo da unidade no eixo X, checagem de faixa fisica)
SWEEP_PARAMS = ("temperature", "porosity", "acid_concentration", "wellbore_diameter", "payzone_thickness")
UI_SWEEP_PARAMS = ("temperature", "porosity", "acid_concentration", "wellbore_diameter", "payzone_thickness")


def _in_open_unit(v):
    return 0.0 < v < 1.0


_RANGES = {
    "temperature": (lambda v: v > 0.0, "temperature must be above absolute zero (> 0 K)"),
    "porosity": (_in_open_unit, "porosity must be strictly between 0 and 1"),
    "acid_concentration": (_in_open_unit, "acid concentration must be strictly between 0 and 1"),
    "wellbore_diameter": (lambda v: v > 0.0, "wellbore diameter must be positive"),
    "payzone_thickness": (lambda v: v > 0.0, "payzone thickness must be positive"),
}


def validate_sweep(sweep_param, minimum, maximum, steps):
    """Levanta ValueError com mensagem por campo ("minimum: ...", "maximum: ...")
    ANTES de qualquer calculo. Min >= max e rejeitado; valores fora da faixa
    fisica do parametro tambem."""
    if sweep_param not in _RANGES:
        raise ValueError(f"sweep_param: unknown parameter {sweep_param!r}")
    ok, msg = _RANGES[sweep_param]
    if not np.isfinite(minimum) or not ok(minimum):
        raise ValueError(f"minimum: {msg}")
    if not np.isfinite(maximum) or not ok(maximum):
        raise ValueError(f"maximum: {msg}")
    if minimum >= maximum:
        raise ValueError("minimum: must be lower than maximum")
    if steps < 2:
        raise ValueError("steps: at least 2 points are required")


def radial_optimum_sweep(
    *,
    sweep_param,
    minimum,
    maximum,
    steps,
    target_mode,
    target,
    acid_type_cls,
    acid_concentration,
    rock_type,
    porosity,
    temperature_k,
    wellbore_radius_in,
    payzone_thickness_ft,
    flow_min_m3s,
    flow_max_m3s,
):
    """Retorna dict com sweep_values / optimum_rate / optimum_volume (paralelos),
    has_clipped_volume e skipped_values (valores sem minimo interior fisico).

    Regra de corte identica ao Design Plot: no primeiro ponto com
    V_opt > 1000 gal/ft marca has_clipped_volume e ENCERRA a serie ali
    (nao descarta em silencio -- a flag sobe e o frontend mostra o aviso)."""
    validate_sweep(sweep_param, minimum, maximum, steps)

    q_lo, q_hi = opt_search_window(flow_min_m3s, flow_max_m3s)
    values = np.linspace(minimum, maximum, steps)

    sweep_values, rates, volumes, skipped = [], [], [], []
    has_clipped = False
    first_clipped = None
    outside = []

    for x in values:
        x = float(x)
        p = dict(
            acid_concentration=acid_concentration, porosity=porosity,
            temperature_k=temperature_k, wellbore_radius_in=wellbore_radius_in,
            payzone_thickness_ft=payzone_thickness_ft,
        )
        if sweep_param == "temperature":
            p["temperature_k"] = x
        elif sweep_param == "porosity":
            p["porosity"] = x
        elif sweep_param == "acid_concentration":
            p["acid_concentration"] = x
        elif sweep_param == "wellbore_diameter":
            p["wellbore_radius_in"] = x / 2.0
        elif sweep_param == "payzone_thickness":
            p["payzone_thickness_ft"] = x

        master = RadialCurveMaster(acid_type_cls=acid_type_cls, rock_type=rock_type, **p)
        geo = master.geometry
        model = PVBtRadial(
            geo, a=master.acidsetup.a, b=master.acidsetup.b, n=master.acidsetup.n,
            k0=master.acidsetup.k0, Dm=master.Dm, C_Ao=master.acid_concentration,
            X=master.X, flowrate_m3s=1e-5, f=master.f,
        )
        lam = target_to_lambda(target, target_mode, geo.beta, geo.L)

        try:
            q_opt, v_opt = model.optimum_flowrate(lam, q_lo, q_hi)
        except ValueError:
            skipped.append(x)
            continue

        h_ft = p["payzone_thickness_ft"]
        q_norm = q_opt * M3_TO_GAL * 60.0 / h_ft
        v_norm = v_opt * M3_TO_GAL / h_ft

        if v_norm > VOLUME_CEILING_GAL_FT:
            has_clipped = True
            first_clipped = x
            break

        if sweep_param == "temperature" and not (T_CALIBRATED_K[0] <= x <= T_CALIBRATED_K[1]):
            outside.append(x)
        sweep_values.append(x)
        rates.append(q_norm)
        volumes.append(v_norm)

    return {
        "sweep_param": sweep_param,
        "sweep_values": sweep_values,
        "optimum_rate": rates,
        "optimum_volume": volumes,
        "has_clipped_volume": has_clipped,
        "first_clipped_value": first_clipped,
        "skipped_values": skipped,
        "outside_calibrated_range": outside,
    }
