from fastapi import APIRouter, Depends, HTTPException
from app.schemas import AnalicalInput, PVBtOutputAnalitical
from app.services.PVBTfunc import AcidType, PVBtMaster
from app.core.security import get_current_user
from app.services.tools import get_correct_param
router = APIRouter()

@router.post("/pvbtanalitical", response_model=PVBtOutputAnalitical)
def calculate_pvbt(data: AnalicalInput):
    if data.flow_regime == 'radial':
        raise HTTPException(
            status_code=400,
            detail="Radial Optimum Analysis is served by /pvbtradialoptimum; /pvbtanalitical is linear-only.",
        )
    return get_correct_param(data)
