from fastapi import APIRouter
from app.schemas import PVBtInputPoint
from app.services.tools import getparam
router = APIRouter()

@router.post("/getparameters")
def calculate_pvbt(data: PVBtInputPoint):
    response = getparam(data)
    
    
    
    return response
