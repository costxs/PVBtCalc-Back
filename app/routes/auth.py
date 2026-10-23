from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core import supabase_gateway as gateway
from app.core.rate_limit import auth_limiter
from app.core.security import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["Auth"], dependencies=[Depends(auth_limiter)])


class Credentials(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1, max_length=128)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name required")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=2048)


def _guard(fn, *args):
    try:
        return fn(*args)
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)


@router.post("/register")
def register(data: Registration):
    return _guard(gateway.sign_up, data.email.strip(), data.password, data.name)


@router.post("/login")
def login(data: Credentials):
    return _guard(gateway.sign_in, data.email.strip(), data.password)


@router.post("/refresh")
def refresh(data: RefreshRequest):
    return _guard(gateway.refresh, data.refresh_token)


@router.post("/logout", status_code=204)
def logout(token: str = Depends(oauth2_scheme)):
    gateway.sign_out(token)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/visit", status_code=204)
def visit(user: dict = Depends(get_current_user)):
    """Registra a visita usando a identidade do token (nunca dados vindos do corpo)."""
    _guard(gateway.log_visit, user)
