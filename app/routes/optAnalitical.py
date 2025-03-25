from fastapi import APIRouter, Depends
from app.schemas import AnalicalInput, PVBtOutputAnalitical
from app.services.PVBTfunc import AcidType, PVBtMaster
from app.core.security import get_current_user
from app.services.tools import get_correct_param
router = APIRouter()

@router.post("/pvbtanalitical", response_model=PVBtOutputAnalitical)
def calculate_pvbt(data: AnalicalInput, current_user:dict = Depends(get_current_user)):
    return get_correct_param(data)
