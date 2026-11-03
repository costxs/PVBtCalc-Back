from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core import config
from app.core import db_gateway as gateway

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)):
    """Exige sessao valida: Bearer token (frontend) ou o cookie de sessao assinado."""
    try:
        if token:
            user = gateway.get_user(token)
        else:
            cookie = request.cookies.get(config.SESSION_COOKIE)
            user = gateway.get_user(cookie, kind="refresh") if cookie else None
    except gateway.GatewayError as e:
        raise HTTPException(status_code=e.status, detail=e.code)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth.err_session_expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: dict = Depends(get_current_user)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin.err_forbidden")
    return user
