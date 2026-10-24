"""Unico ponto de contato com o Supabase (Auth + tabela `visits`).

Usa so a stdlib (urllib) e funcoes sincronas: o FastAPI as executa em threadpool.
Os erros do Supabase nunca vazam ao cliente: viram `GatewayError` com um codigo
estavel (chave i18n do frontend).
"""
import hashlib
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from app.core import config

_TIMEOUT = 10
_USER_CACHE_TTL = 30
_USER_CACHE_MAX = 2048


class GatewayError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def _call(method: str, path: str, *, body=None, key: str, bearer: str | None = None):
    if not config.SUPABASE_URL or not key:
        raise GatewayError(503, "auth.err_server_unavailable")
    headers = {"apikey": key, "Authorization": f"Bearer {bearer or key}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(config.SUPABASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"{}")
        except ValueError:
            payload = {}
        return e.code, payload
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GatewayError(503, "auth.err_server_unavailable")


def _auth_error(status: int, payload: dict) -> GatewayError:
    text = " ".join(str(payload.get(k, "")) for k in ("error_code", "code", "msg", "message", "error_description")).lower()
    if "email_not_confirmed" in text or "not confirmed" in text:
        return GatewayError(403, "auth.err_email_not_confirmed")
    if "already" in text:
        return GatewayError(409, "auth.err_email_in_use")
    if "weak_password" in text or (status == 422 and "password" in text):
        return GatewayError(422, "auth.err_password_min")
    if status == 429 or "rate" in text:
        return GatewayError(429, "auth.err_rate_limited")
    if status >= 500:
        return GatewayError(503, "auth.err_server_unavailable")
    return GatewayError(401, "auth.err_invalid_credentials")


def is_admin(user_id: str) -> bool:
    """Admin = linha em public.admins. Consulta com a chave de servico; falha => nao admin."""
    if not user_id or not config.SUPABASE_SERVICE_ROLE_KEY:
        return False
    try:
        status, rows = _call(
            "GET", f"/rest/v1/admins?select=user_id&user_id=eq.{urllib.parse.quote(user_id)}",
            key=config.SUPABASE_SERVICE_ROLE_KEY,
        )
    except GatewayError:
        return False
    return status == 200 and isinstance(rows, list) and len(rows) > 0


def _session(payload: dict) -> dict:
    user = payload.get("user") or {}
    meta = user.get("user_metadata") or {}
    email = user.get("email") or ""
    return {
        "access_token": payload["access_token"],
        "refresh_token": payload["refresh_token"],
        "expires_in": int(payload.get("expires_in", 3600)),
        "user": {
            "id": user.get("id", ""), "email": email, "name": meta.get("name") or email,
            "is_admin": is_admin(user.get("id", "")),
        },
    }


def sign_up(email: str, password: str, name: str) -> dict:
    status, payload = _call(
        "POST", "/auth/v1/signup",
        body={"email": email, "password": password, "data": {"name": name}},
        key=config.SUPABASE_PUBLISHABLE_KEY,
    )
    if status >= 400:
        raise _auth_error(status, payload)
    if not payload.get("access_token"):
        return {"confirm_email": True}
    return {"confirm_email": False, "session": _session(payload)}


def sign_in(email: str, password: str) -> dict:
    status, payload = _call(
        "POST", "/auth/v1/token?grant_type=password",
        body={"email": email, "password": password}, key=config.SUPABASE_PUBLISHABLE_KEY,
    )
    if status >= 400:
        raise _auth_error(status, payload)
    return _session(payload)


def refresh(refresh_token: str) -> dict:
    status, payload = _call(
        "POST", "/auth/v1/token?grant_type=refresh_token",
        body={"refresh_token": refresh_token}, key=config.SUPABASE_PUBLISHABLE_KEY,
    )
    if status >= 500:
        raise _auth_error(status, payload)
    if status >= 400:
        raise GatewayError(401, "auth.err_session_expired")
    return _session(payload)


_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _forget(token: str) -> None:
    with _cache_lock:
        _cache.pop(_digest(token), None)


def sign_out(access_token: str) -> None:
    _forget(access_token)
    try:
        _call("POST", "/auth/v1/logout", key=config.SUPABASE_PUBLISHABLE_KEY, bearer=access_token)
    except GatewayError:
        pass


def get_user(access_token: str) -> dict | None:
    """Valida o token no proprio Supabase (respeita logout/revogacao).
    Resultado em cache curto para nao consultar o Auth a cada requisicao."""
    key, now = _digest(access_token), time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    status, payload = _call("GET", "/auth/v1/user", key=config.SUPABASE_PUBLISHABLE_KEY, bearer=access_token)
    if status >= 500:
        raise GatewayError(503, "auth.err_server_unavailable")
    if status >= 400 or not payload.get("id"):
        return None
    meta = payload.get("user_metadata") or {}
    email = payload.get("email") or ""
    user = {
        "id": payload["id"], "email": email, "name": meta.get("name") or email,
        "is_admin": is_admin(payload["id"]),
    }
    with _cache_lock:
        if len(_cache) >= _USER_CACHE_MAX:
            _cache.clear()
        _cache[key] = (now + _USER_CACHE_TTL, user)
    return user


def log_visit(user: dict) -> None:
    status, _ = _call(
        "POST", "/rest/v1/visits",
        body={"user_id": user["id"], "name": user["name"], "email": user["email"]},
        key=config.SUPABASE_SERVICE_ROLE_KEY,
    )
    if status >= 400:
        raise GatewayError(502, "auth.err_server_unavailable")


def list_visits(limit: int = 10000) -> list[dict]:
    status, rows = _call(
        "GET", f"/rest/v1/visits?select=id,user_id,name,email,visited_at&order=visited_at.desc&limit={int(limit)}",
        key=config.SUPABASE_SERVICE_ROLE_KEY,
    )
    if status >= 400 or not isinstance(rows, list):
        raise GatewayError(502, "auth.err_server_unavailable")
    return rows


def list_users(max_pages: int = 20) -> list[dict]:
    """Contas cadastradas (Auth admin API); so o necessario para o painel."""
    users: list[dict] = []
    for page in range(1, max_pages + 1):
        status, payload = _call(
            "GET", f"/auth/v1/admin/users?page={page}&per_page=1000", key=config.SUPABASE_SERVICE_ROLE_KEY,
        )
        if status >= 400 or not isinstance(payload, dict):
            raise GatewayError(502, "auth.err_server_unavailable")
        batch = payload.get("users") or []
        for u in batch:
            meta = u.get("user_metadata") or {}
            users.append({
                "user_id": u.get("id"), "name": meta.get("name") or u.get("email") or "",
                "email": u.get("email") or "", "created_at": u.get("created_at"),
                "last_sign_in_at": u.get("last_sign_in_at"),
            })
        if len(batch) < 1000:
            break
    return users
