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


# --- simulacoes salvas (ate 10 por conta) -------------------------------------------

from fastapi import Body, Path  # noqa: E402
from pydantic import Field  # noqa: E402

from app.core import simulations_store as sims  # noqa: E402

PATCH_KEYS = {
    "label", "flowRegime", "rock", "acid", "porosity", "concentration", "temperature",
    "targets", "curves", "designSeries", "skinSeries",
}
SimId = Path(min_length=1, max_length=200)


def _guard(fn, *args):
    try:
        return fn(*args)
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)


@router.get("/simulations")
def list_simulations(user: dict = Depends(get_current_user)):
    """Resumo das simulacoes salvas (sem curvas), da mais recente para a mais antiga."""
    return {"max": sims.MAX_SAVED, "items": _guard(sims.list_summaries, user["id"])}


@router.get("/simulations/{sim_id:path}")
def get_simulation(sim_id: str = SimId, user: dict = Depends(get_current_user)):
    snap = _guard(sims.get, user["id"], sim_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="sim.err_not_found")
    return snap


@router.put("/simulations/{sim_id:path}")
def save_simulation(sim_id: str = SimId, patch: dict = Body(...), user: dict = Depends(get_current_user)):
    """Grava (ou completa) uma simulacao. Devolve as que sairam por causa do limite."""
    clean = {k: v for k, v in patch.items() if k in PATCH_KEYS}
    if clean.get("flowRegime") not in ("linear", "radial"):
        raise HTTPException(status_code=422, detail="sim.err_invalid")
    if "label" in clean and not (isinstance(clean["label"], str) and 0 < len(clean["label"]) <= 200):
        raise HTTPException(status_code=422, detail="sim.err_invalid")
    return {"evicted": _guard(sims.upsert, user["id"], sim_id, clean)}


class Rename(BaseModel):
    label: str = Field(min_length=1, max_length=200)


@router.patch("/simulations/{sim_id:path}", status_code=204)
def rename_simulation(data: Rename, sim_id: str = SimId, user: dict = Depends(get_current_user)):
    if not _guard(sims.rename, user["id"], sim_id, data.label.strip() or sim_id):
        raise HTTPException(status_code=404, detail="sim.err_not_found")


@router.delete("/simulations/{sim_id:path}", status_code=204)
def delete_simulation(sim_id: str = SimId, user: dict = Depends(get_current_user)):
    _guard(sims.delete, user["id"], sim_id)


@router.delete("/simulations", status_code=204)
def delete_all_simulations(user: dict = Depends(get_current_user)):
    _guard(sims.delete_all, user["id"])
