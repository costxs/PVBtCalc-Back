from fastapi import APIRouter
from app.schemas import RadialOptimumSweepInput, RadialOptimumSweepOutput
from app.services.PVBTfunc import AcidType
from app.services.radial_optimum_sweep import radial_optimum_sweep
from app.services.units import flowrate_to_m3s

router = APIRouter()


@router.post("/pvbtradialoptimum", response_model=RadialOptimumSweepOutput)
def radial_optimum(data: RadialOptimumSweepInput):
    return radial_optimum_sweep(
        sweep_param=data.sweep_param,
        minimum=data.minimum,
        maximum=data.maximum,
        steps=data.steps,
        target_mode=data.target_mode,
        target=data.target,
        acid_type_cls=AcidType.getAcidTypeByStr(data.acid_system),
        acid_concentration=data.acid_concentration,
        rock_type=data.rock_type,
        porosity=data.porosity,
        temperature_k=data.temperature_k,
        wellbore_radius_in=data.wellbore_radius_in,
        payzone_thickness_ft=data.payzone_thickness_ft,
        flow_min_m3s=flowrate_to_m3s(data.flow_min_bbl_min, "bbl_min"),
        flow_max_m3s=flowrate_to_m3s(data.flow_max_bbl_min, "bbl_min"),
    )
