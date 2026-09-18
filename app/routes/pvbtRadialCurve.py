from fastapi import APIRouter, Depends
from app.schemas import RadialCurveInput, RadialCurveOutput
from app.services.PVBTfunc import AcidType
from app.services.PVBTradialFunc import RadialCurveMaster
from app.services.units import flowrate_to_m3s
from app.core.security import get_current_user

router = APIRouter()


@router.post("/pvbtradialcurve", response_model=RadialCurveOutput)
def calculate_pvbt_radial(data: RadialCurveInput):
    master = RadialCurveMaster(
        acid_type_cls=AcidType.getAcidTypeByStr(data.system.acid_system),
        acid_concentration=data.system.acid_concentration,
        rock_type=data.system.rock_type,
        porosity=data.system.porosity,
        temperature_k=data.system.temperature_k,
        wellbore_radius_in=data.geometry.wellbore_radius_in,
        payzone_thickness_ft=data.geometry.payzone_thickness_ft,
        drainage_radius_ft=data.geometry.drainage_radius_ft,
    )

    # A UI coleta o sweep radial em bbl/min (SimuCard.tsx:283), nao cm3/min.
    flow_min_m3s = flowrate_to_m3s(data.flowrate_sweep.min, "bbl_min")
    flow_max_m3s = flowrate_to_m3s(data.flowrate_sweep.max, "bbl_min")

    curves = master.build_curves(
        target_mode=data.radial_targets.target_mode,
        targets_display=data.radial_targets.targets,
        flow_min_m3s=flow_min_m3s,
        flow_max_m3s=flow_max_m3s,
        steps=data.flowrate_sweep.steps,
    )

    return {
        # Fase 9: "pvbt" so quando geometry.drainage_radius_ft foi informado;
        # senao "volume" (frontend omite a coluna PVBt). Antes saia chumbado.
        "output_mode": master.output_mode,
        "curves": curves,
        "parameters": master.get_adjusted_parameters(),
    }
