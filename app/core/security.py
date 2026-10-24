from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core import supabase_gateway as gateway

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)):
    """Exige uma sessao Supabase valida (token verificado no Auth, nao so decodificado)."""
    try:
        user = gateway.get_user(token)
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
