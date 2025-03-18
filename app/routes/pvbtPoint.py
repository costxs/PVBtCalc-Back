from fastapi import APIRouter
from app.schemas import PVBtInputPoint, PVBtOutputPoint
from app.services.PVBTfunc import AcidType, PVBtMaster

router = APIRouter()

@router.post("/pvbtpoint", response_model=PVBtOutputPoint)
def calculate_pvbt(data: PVBtInputPoint):
    master = PVBtMaster(
        acidtype=AcidType.getAcidTypeByStr(data.acid_type),
        acid_concentration=data.acid_concentration,
        core_diameter=data.core_diameter,
        core_length=data.core_length,
        core_porosity=data.core_porosity,
        rock_type=data.rock_type,
        temperature=data.temperature,
        flowrate=data.flowrate,
    )
    
    
    return {"pore_volume_to_breakthrough": master.PVBtPointCalculator()}
