from fastapi import APIRouter
from app.schemas import PVBtInputCurve, PVBtOutputCurveWhithDetails
from app.services.PVBTfunc import AcidType, PVBtMaster

router = APIRouter()

@router.post("/pvbtcurve", response_model=PVBtOutputCurveWhithDetails)
def calculate_pvbt(data: PVBtInputCurve):
    master = PVBtMaster(
        acidtype=AcidType.getAcidTypeByStr(data.acid_type),
        acid_concentration=data.acid_concentration,
        core_diameter=data.core_diameter,
        core_length=data.core_length,
        core_porosity=data.core_porosity,
        rock_type=data.rock_type,
        temperature=data.temperature,
        flowrate=data.flowrate,
        minimun_flowrate=data.minimum_flowrate,
        step_numbers=data.step_numbers,
    )
    pvbt, flowrates, velocity, ida, volumetobt, timetobt, wormhole, darcy = master.PVBtCurveCalculatorWhiteDetails()
    
    
    return {
        "pvbtpoints": pvbt, 
        "flowratepoints": flowrates,
        "insterticialvelocity":velocity,
        "ida":ida,
        "volumetobt":volumetobt,
        "timetobt":timetobt,
        "wormholevelocity":wormhole,
        "darcyvelocity":darcy
        }
