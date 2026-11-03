"""Unico ponto de contato com o banco PostgreSQL (contas, admins e visitas).

As contas continuam na tabela `auth.users` copiada do Supabase: a senha fica em
`encrypted_password` (bcrypt) e o nome em `raw_user_meta_data->>'name'`. Por isso
os usuarios existentes entram com a mesma senha de antes.

A sessao e um token assinado com SECRET_KEY (itsdangerous). O mesmo token vai no
corpo da resposta (o frontend usa como Bearer) e num cookie HttpOnly.

Funcoes sincronas: o FastAPI as executa em threadpool. Erros do banco nunca vazam
ao cliente: viram `GatewayError` com um codigo estavel (chave i18n do frontend).
"""
import hashlib
import json
import threading
import time
import uuid

import bcrypt
import psycopg
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core import config

_USER_CACHE_TTL = 30
_USER_CACHE_MAX = 2048
# Hash qualquer para gastar o mesmo tempo quando o e-mail nao existe.
_DUMMY_HASH = bcrypt.hashpw(b"pvbtcalc-dummy", bcrypt.gensalt(10))


class GatewayError(Exception):
    def __init__(self, status: int, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


# --- conexao -----------------------------------------------------------------

_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    global _pool
    if not config.DATABASE_URL:
        raise GatewayError(503, "auth.err_server_unavailable")
    with _pool_lock:
        if _pool is None:
            _pool = ConnectionPool(
                config.DATABASE_URL, min_size=1, max_size=config.DB_POOL_MAX,
                kwargs={"row_factory": dict_row, "connect_timeout": 10},
                open=False, check=ConnectionPool.check_connection,
            )
            _pool.open(wait=False)
    return _pool


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None


def _query(sql: str, params=(), *, fetch: str = "all"):
    try:
        with _get_pool().connection(timeout=10) as conn:
            cur = conn.execute(sql, params)
            if fetch == "one":
                return cur.fetchone()
            if fetch == "all":
                return cur.fetchall()
            return None
    except GatewayError:
        raise
    except psycopg.errors.UniqueViolation:
        raise GatewayError(409, "auth.err_email_in_use")
    except Exception:
        import traceback
        traceback.print_exc()
        raise GatewayError(503, "auth.err_server_unavailable")


# --- tokens --------------------------------------------------------------------

def _serializer(kind: str) -> URLSafeTimedSerializer:
    if not config.SECRET_KEY:
        raise GatewayError(503, "auth.err_server_unavailable")
    return URLSafeTimedSerializer(config.SECRET_KEY, salt=f"pvbtcalc-{kind}")


def _make_token(kind: str, user_id: str) -> str:
    return _serializer(kind).dumps({"uid": user_id})


def _read_token(kind: str, token: str, max_age: int) -> str | None:
    try:
        data = _serializer(kind).loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    uid = data.get("uid") if isinstance(data, dict) else None
    return uid if isinstance(uid, str) and uid else None


# --- usuarios --------------------------------------------------------------------

# A copia de auth.users pode nao ter todas as colunas do Supabase. So id, email e
# encrypted_password sao obrigatorias; as demais sao usadas se existirem.
_users_cols: frozenset[str] | None = None


def _cols() -> frozenset[str]:
    global _users_cols
    if _users_cols is None:
        rows = _query(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'auth' AND table_name = 'users'"
        )
        if rows:  # nao guarda resultado vazio (tabela inacessivel): tenta de novo depois
            _users_cols = frozenset(r["column_name"] for r in rows)
            print(f"auth.users: colunas encontradas = {sorted(_users_cols)}")
        return frozenset(r["column_name"] for r in rows)
    return _users_cols


def _name_sql(cols: frozenset[str]) -> str:
    for meta in ("raw_user_meta_data", "user_metadata"):
        if meta in cols:
            return f"({meta}::jsonb ->> 'name')"
    return "name::text" if "name" in cols else "NULL::text"


def _opt(col: str, cols: frozenset[str], cast: str = "timestamptz") -> str:
    return f"{col}" if col in cols else f"NULL::{cast}"


def is_admin(user_id: str) -> bool:
    """Admin = linha em public.admins. Falha de consulta => nao admin."""
    if not user_id:
        return False
    try:
        row = _query("SELECT 1 AS ok FROM public.admins WHERE user_id::text = %s LIMIT 1", (user_id,), fetch="one")
    except GatewayError:
        return False
    return row is not None


def _profile(row: dict) -> dict:
    email = row.get("email") or ""
    return {"id": row["id"], "email": email, "name": row.get("name") or email, "is_admin": is_admin(row["id"])}


def _load_user(user_id: str) -> dict | None:
    row = _query(
        f"SELECT id::text AS id, email, {_name_sql(_cols())} AS name FROM auth.users WHERE id::text = %s",
        (user_id,), fetch="one",
    )
    return _profile(row) if row else None


def _session(user: dict) -> dict:
    return {
        "access_token": _make_token("access", user["id"]),
        "refresh_token": _make_token("refresh", user["id"]),
        "expires_in": config.ACCESS_TOKEN_TTL,
        "user": user,
    }


def _check_password(password: str, hashed: str | None) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), (hashed or "").encode() or _DUMMY_HASH)
    except ValueError:
        # Conta sem senha (ex.: login social) ou hash invalido.
        return False


def sign_up(email: str, password: str, name: str) -> dict:
    cols = _cols()
    exists = _query("SELECT 1 AS ok FROM auth.users WHERE lower(email) = lower(%s) LIMIT 1", (email,), fetch="one")
    if exists:
        raise GatewayError(409, "auth.err_email_in_use")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(10)).decode()
    fields = {"id": ("%s", str(uuid.uuid4())), "email": ("lower(%s)", email), "encrypted_password": ("%s", hashed)}
    meta = next((m for m in ("raw_user_meta_data", "user_metadata") if m in cols), None)
    if meta:
        fields[meta] = ("%s::jsonb", json.dumps({"name": name}))
    elif "name" in cols:
        fields["name"] = ("%s", name)
    for col in ("email_confirmed_at", "created_at", "updated_at"):
        if col in cols:
            fields[col] = ("now()", None)
    names = ", ".join(fields)
    values = ", ".join(v[0] for v in fields.values())
    params = tuple(v[1] for v in fields.values() if v[0] != "now()")
    row = _query(
        f"INSERT INTO auth.users ({names}) VALUES ({values}) RETURNING id::text AS id, email, {_name_sql(cols)} AS name",
        params, fetch="one",
    )
    return {"confirm_email": False, "session": _session(_profile(row))}


def sign_in(email: str, password: str) -> dict:
    cols = _cols()
    row = _query(
        f"""SELECT id::text AS id, email, encrypted_password, {_name_sql(cols)} AS name,
                   {_opt("email_confirmed_at", cols)} AS email_confirmed_at
            FROM auth.users WHERE lower(email) = lower(%s) LIMIT 1""",
        (email,), fetch="one",
    )
    if not _check_password(password, row and row.get("encrypted_password")) or row is None:
        raise GatewayError(401, "auth.err_invalid_credentials")
    if "email_confirmed_at" in cols and row.get("email_confirmed_at") is None:
        raise GatewayError(403, "auth.err_email_not_confirmed")
    if "last_sign_in_at" in cols:
        try:
            _query("UPDATE auth.users SET last_sign_in_at = now() WHERE id::text = %s", (row["id"],), fetch="none")
        except GatewayError:
            pass  # so informativo: nao impede o login
    return _session(_profile(row))


def refresh(refresh_token: str) -> dict:
    uid = _read_token("refresh", refresh_token, config.SESSION_TTL)
    user = _load_user(uid) if uid else None
    if user is None:
        raise GatewayError(401, "auth.err_session_expired")
    return _session(user)


_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def sign_out(access_token: str) -> None:
    with _cache_lock:
        _cache.pop(_digest(access_token), None)


def get_user(token: str, *, kind: str = "access") -> dict | None:
    """Valida a assinatura/validade do token e confirma que a conta ainda existe.
    Resultado em cache curto para nao consultar o banco a cada requisicao."""
    max_age = config.ACCESS_TOKEN_TTL if kind == "access" else config.SESSION_TTL
    uid = _read_token(kind, token, max_age)
    if not uid:
        return None
    key, now = _digest(f"{kind}:{token}"), time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    user = _load_user(uid)
    if user is None:
        return None
    with _cache_lock:
        if len(_cache) >= _USER_CACHE_MAX:
            _cache.clear()
        _cache[key] = (now + _USER_CACHE_TTL, user)
    return user


# --- visitas / painel admin -------------------------------------------------------

def log_visit(user: dict) -> None:
    _query(
        "INSERT INTO public.visits (user_id, name, email) VALUES (%s, %s, %s)",
        (user["id"], user["name"], user["email"]), fetch="none",
    )


def list_visits(limit: int = 10000) -> list[dict]:
    return _query(
        """SELECT id, user_id::text AS user_id, name, email, visited_at
           FROM public.visits ORDER BY visited_at DESC LIMIT %s""",
        (int(limit),),
    )


def list_users(limit: int = 20000) -> list[dict]:
    """Contas cadastradas; so o necessario para o painel."""
    cols = _cols()
    order = "created_at" if "created_at" in cols else "email"
    rows = _query(
        f"""SELECT id::text AS user_id, email, {_name_sql(cols)} AS name,
                   {_opt("created_at", cols)} AS created_at, {_opt("last_sign_in_at", cols)} AS last_sign_in_at
            FROM auth.users ORDER BY {order} LIMIT %s""",
        (int(limit),),
    )
    return [
        {
            "user_id": r["user_id"], "name": r.get("name") or r.get("email") or "",
            "email": r.get("email") or "", "created_at": r.get("created_at"),
            "last_sign_in_at": r.get("last_sign_in_at"),
        }
        for r in rows
    ]
