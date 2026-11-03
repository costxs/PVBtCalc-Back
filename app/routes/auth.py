from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app.core import config
from app.core import db_gateway as gateway
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
    refresh_token: str | None = Field(default=None, min_length=1, max_length=2048)


def _guard(fn, *args):
    try:
        return fn(*args)
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)


def _set_cookie(response: Response, session: dict | None) -> None:
    """Sessao tambem num cookie HttpOnly assinado (SECRET_KEY)."""
    if session:
        response.set_cookie(
            config.SESSION_COOKIE, session["refresh_token"], max_age=config.SESSION_TTL,
            httponly=True, secure=config.COOKIE_SECURE, samesite="lax", path="/",
        )


@router.post("/register")
def register(data: Registration, response: Response):
    result = _guard(gateway.sign_up, data.email.strip(), data.password, data.name)
    _set_cookie(response, result.get("session"))
    return result


@router.post("/login")
def login(data: Credentials, response: Response):
    session = _guard(gateway.sign_in, data.email.strip(), data.password)
    _set_cookie(response, session)
    return session


@router.post("/refresh")
def refresh(request: Request, response: Response, data: RefreshRequest | None = None):
    token = (data.refresh_token if data else None) or request.cookies.get(config.SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="auth.err_session_expired")
    session = _guard(gateway.refresh, token)
    _set_cookie(response, session)
    return session


@router.post("/logout", status_code=204)
def logout(response: Response, token: str | None = Depends(oauth2_scheme)):
    if token:
        gateway.sign_out(token)
    response.delete_cookie(config.SESSION_COOKIE, path="/", secure=config.COOKIE_SECURE, httponly=True, samesite="lax")


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/visit", status_code=204)
def visit(user: dict = Depends(get_current_user)):
    """Registra a visita usando a identidade do token (nunca dados vindos do corpo)."""
    _guard(gateway.log_visit, user)
