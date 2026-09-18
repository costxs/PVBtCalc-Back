from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
class PVBtInputPoint(BaseModel):
    acid_type: str
    acid_concentration: float
    core_diameter: float
    core_length: float
    core_porosity: float
    rock_type: str
    temperature: float
    flowrate: float

class PVBtInputCurve(BaseModel):
    acid_type: str
    acid_concentration: float
    core_diameter: float
    core_length: float
    core_porosity: float
    rock_type: str
    temperature: float
    flowrate: float
    minimum_flowrate: float
    step_numbers: int

class AnalicalInput(BaseModel):
    analitical_param: str
    acid_type: str
    acid_concentration: float
    core_diameter: float
    core_length: float
    core_porosity: float
    rock_type: str
    temperature: float
    flowrate: float
    minimum_analitical: float
    step_numbers: int
    flow_regime: str = "linear"
    target: Optional[float] = None
    target_mode: Optional[str] = None
    wellbore_radius_in: Optional[float] = None
    payzone_thickness_ft: Optional[float] = None

# pvbt / volumetobt / timetobt podem vir None: os calculadores em
# PVBTfunc.py retornam None quando exp_term = Dn*lambda > 700 (sem
# breakthrough dentro do dominio numerico). O front ja trata null
# (Results.getFormattedVal -> '-', Chart -> 0). Sem o Optional, o
# response_model dispara ResponseValidationError -> 500 sem header CORS.
class PVBtOutputPoint(BaseModel):
    pore_volume_to_breakthrough: Optional[float]

class PVBtOutputCurveWhithDetails(BaseModel):
    pvbtpoints: List[Optional[float]]
    flowratepoints: List[float]
    insterticialvelocity: List[float]
    ida: List[float]
    volumetobt: List[Optional[float]]
    timetobt: List[Optional[float]]
    wormholevelocity: List[float]
    darcyvelocity: List[float]
    # Janela de validade da vazao no regime LINEAR (Fase 6). Arrays paralelos
    # a flowratepoints (SoA -- mesma decisao de design que RadialCurveResult,
    # nao AoS). Unidades em cm3/min (escala de core), convertidas de m3/s via
    # app.services.units -- ver app.services.linear_validity.
    #   status[i]: "ok" | "clipped" ("clipped" = exp_term > 700 -> pvbt None,
    #     mesmo criterio de corte de hoje, so nomeado; List[Optional[str]] por
    #     consistencia de contrato, na pratica nunca None).
    #   within_validity_range[i]: False = vazao fora de [q_opt/10, q_opt*10].
    #   metadata: None na degradacao (optimum_flowrate_linear sem minimo
    #     interior); nesse caso within_validity_range vem todo True.
    status: List[Optional[str]]
    within_validity_range: List[bool]
    metadata: Optional[dict]

class PVBtOutputAnalitical(BaseModel):
    analyzed:str
    pvbtpoints: List[Optional[float]]
    analiticalpoints: List[float]
    insterticialvelocity: List[float]
    ida: List[float]
    volumetobt: List[Optional[float]]
    timetobt: List[Optional[float]]
    wormholevelocity: List[float]
    darcyvelocity: List[float]

class PVBtOutputPointWhithDetails(BaseModel):
    PVBtPoints: Optional[float]
    FlowratePoints: float
    intersticialVelocity: float
    iDa: float
    volumeToBt: Optional[float]
    timeToBt: Optional[float]
    wormholeVelocity: float
    darcyVelocity: float


class PVBtOutputCurve(BaseModel):
    PVBtPoints: List[Optional[float]]
    FlowratePoints: List[float]


class RadialSystem(BaseModel):
    rock_type: str
    porosity: float
    acid_system: str
    acid_concentration: float
    temperature_k: float = Field(..., ge=283.0, le=478.0)

class RadialGeometryInput(BaseModel):
    wellbore_radius_in: float
    payzone_thickness_ft: float
    drainage_radius_ft: Optional[float] = None

class RadialTargetsInput(BaseModel):
    target_mode: str  # "length" | "skin"
    targets: List[float]

class FlowrateSweepInput(BaseModel):
    min: float
    max: float
    steps: int

class RadialCurveInput(BaseModel):
    simulation_id: Optional[Any] = None
    system: RadialSystem
    geometry: RadialGeometryInput
    radial_targets: RadialTargetsInput
    flowrate_sweep: FlowrateSweepInput

class DesignPlotInput(RadialCurveInput):
    temperatures_to_compare: List[float]

# Janela de validade da vazao (Fase 2, unidade trocada para gal/(ft.min) na
# Fase 8): ja convertido de m3/s via app.services.units.flowrate_to_display
# -- nunca cm3/min, bbl/min nem m3/s crus. metadata pode vir None se
# optimum_flowrate nao achar minimo interior mesmo apos alargar a janela;
# nesse caso within_validity_range vem todo True (sem anotacao), nao todo
# False.
class RadialCurveValidity(BaseModel):
    q_opt_gal_ft_min: float
    validity_min_gal_ft_min: float
    validity_max_gal_ft_min: float

class RadialCurveResult(BaseModel):
    target: float
    target_label: str
    flowratepoints: List[float]
    # elemento nulavel (List[Optional[float]]), NAO lista-inteira-nula:
    # onde status[i] == "clipped" (expoente batendo em LIMITE_EXP, regime de
    # vazao ~nula) o valor sai como expm1(700)/K -- a poucas ordens do teto
    # do float64 e prestes a virar inf/nan nao-serializavel. Nesses indices o
    # backend emite None. Mesmo padrao que a Fase 0 aplicou ao Linear
    # (PVBtOutputCurveWhithDetails: exp_term > 700 -> None).
    pvbtpoints: List[Optional[float]]
    acidvolumepoints: List[Optional[float]]
    insterticialvelocity: List[float]
    ida: List[float]
    # volumetobt e o MESMO valor calculado de acidvolumepoints (acid_volume *
    # 1e6) -- nula nos mesmos indices, pelo mesmo motivo.
    volumetobt: List[Optional[float]]
    timetobt: List[Optional[float]]
    wormholevelocity: List[float]
    darcyvelocity: List[float]
    status: List[str]
    # array paralelo a status/flowratepoints -- mesmo indice, mesmo ponto.
    # NAO e objeto-por-ponto (decisao de design: SoA, nao AoS).
    within_validity_range: List[bool]
    metadata: Optional[RadialCurveValidity]

class RadialAdjustedParameters(BaseModel):
    ro: float
    X: float
    x: float
    n: float
    a: float
    b: float
    k0: float
    f: float

class RadialCurveOutput(BaseModel):
    output_mode: str
    curves: List[RadialCurveResult]
    # Bloco de parametros efetivamente carregados pelo backend para este
    # request (acid system + concentracao + temperatura). Existe para que o
    # painel "Adjusted Parameters" do frontend consiga confirmar visualmente
    # qual AcidSetup foi resolvido -- sem isso, um mapeamento string->classe
    # incorreto fica invisivel (so aparece como numero errado la na frente).
    parameters: RadialAdjustedParameters

class SkinEvolutionInput(BaseModel):
    acid_type: str
    acid_concentration: float
    temperature_k: float = Field(..., ge=283.0, le=478.0)
    core_porosity: float
    wellbore_radius_in: float
    payzone_thickness_ft: float
    rock_type: str
    flowrates_to_compare: List[float]
    target: Optional[float] = None

class DesignPlotSeries(BaseModel):
    temperature_k: float
    optimum_rate_series: List[List[float]]
    optimum_volume_series: List[List[float]]

class DesignPlotOutput(BaseModel):
    series: List[DesignPlotSeries]
    has_clipped_volume: bool = False


# --- Export radial (matplotlib figures + workbook) -------------------------
# Contrato de ENTRADA do /export/radial* -- o front reenvia os MESMOS dados
# que ja tem em memoria (RadialCurveResult de /pvbtradialcurve,
# DesignPlotSeries de /designplot, o dict cru de /skinevolution) mais os
# metadados de Inputs e as escolhas de UI (chips ativos, limites de eixo).
# NENHUM campo aqui e recalculado -- so redesenhado/reformatado.

class SkinEvolutionPoint(BaseModel):
    x: float
    y: float
    l_ft: float


class AxisLimitsInput(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None


class ExportInputs(BaseModel):
    simulation_id: str = "—"
    rock_type: str = ""
    acid_type: str = ""
    acid_concentration: Optional[float] = None
    porosity: Optional[float] = None
    temperature_k: Optional[float] = None
    wellbore_size_in: Optional[float] = None
    wellbore_mode: str = "diameter"
    wellbore_radius_in: Optional[float] = None
    payzone_thickness_ft: Optional[float] = None
    flowrate_min_bbl_min: Optional[float] = None
    flowrate_max_bbl_min: Optional[float] = None
    number_of_steps: Optional[int] = None
    targets_label: str = "—"
    flowing_fraction: Optional[float] = None


class RadialExportOptions(BaseModel):
    # Alvo/skin usados pro destaque no Design Plot / Skin (mesmo valor que o
    # front ja calcula pra tabela -- ver export.tsx exportRadialAll).
    target_lengths: Optional[List[float]] = None
    target_skin: Optional[float] = None
    # Chips ativos (quadro de controle do Chart.tsx) -- None = todos ativos.
    active_targets: Optional[List[str]] = None
    active_temperatures: Optional[List[float]] = None
    active_flowrates: Optional[List[str]] = None
    show_optimum_path: bool = True
    show_validity_band: bool = True
    sim_x_limits: Optional[AxisLimitsInput] = None
    sim_y_limits: Optional[AxisLimitsInput] = None
    design_x_limits: Optional[AxisLimitsInput] = None
    design_y_limits: Optional[AxisLimitsInput] = None
    skin_x_limits: Optional[AxisLimitsInput] = None
    skin_y_limits: Optional[AxisLimitsInput] = None


class RadialExportRequest(BaseModel):
    inputs: ExportInputs
    curves: List[RadialCurveResult]
    design_series: List[DesignPlotSeries] = []
    skin_series: Dict[str, List[SkinEvolutionPoint]] = {}
    options: RadialExportOptions = RadialExportOptions()
