from fastapi import APIRouter, Depends
from app.schemas import DesignPlotInput, DesignPlotOutput
from app.services.PVBTfunc import AcidType
from app.services.PVBTradialFunc import RadialCurveMaster
from app.services.units import flowrate_to_m3s
from app.core.security import get_current_user

router = APIRouter()

@router.post("/designplot", response_model=DesignPlotOutput)
def generate_design_plot(data: DesignPlotInput):
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

    flow_min_m3s = flowrate_to_m3s(data.flowrate_sweep.min, "bbl_min")
    flow_max_m3s = flowrate_to_m3s(data.flowrate_sweep.max, "bbl_min")

    result = master.generate_design_plot(
        temperatures_k=data.temperatures_to_compare,
        flow_min_m3s=flow_min_m3s,
        flow_max_m3s=flow_max_m3s,
        target_mode=data.radial_targets.target_mode,
        targets=data.radial_targets.targets
    )
    return result
