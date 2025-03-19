from fastapi import APIRouter, Depends
from app.schemas import PVBtInputPoint
from app.services.tools import getparam
from app.core.security import get_current_user
router = APIRouter()

@router.post("/getparameters")
def calculate_pvbt(data: PVBtInputPoint, current_user:dict = Depends(get_current_user)):
    response = getparam(data)
    
    
    
    return response
