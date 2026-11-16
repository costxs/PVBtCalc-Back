from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core import db_gateway as gateway
from app.core.security import get_current_user

router = APIRouter(prefix="/me", tags=["Me"])


class TrackDone(BaseModel):
    track: Literal["linear", "radial", "export"]


@router.get("/onboarding")
def onboarding(user: dict = Depends(get_current_user)):
    """Trilhas do tour ja concluidas (data) ou pendentes (null) para o usuario logado."""
    try:
        return gateway.get_onboarding(user["id"])
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)


@router.patch("/onboarding", status_code=204)
def onboarding_done(data: TrackDone, user: dict = Depends(get_current_user)):
    """Marca a trilha como concluida (Concluir e Pular gravam igual)."""
    try:
        gateway.mark_onboarding(user["id"], data.track)
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)
