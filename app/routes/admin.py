from fastapi import APIRouter, Depends, HTTPException

from app.core import supabase_gateway as gateway
from app.core.security import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
def overview():
    """Visitas + contas cadastradas para o painel (somente administradores)."""
    try:
        return {"visits": gateway.list_visits(), "users": gateway.list_users()}
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)
