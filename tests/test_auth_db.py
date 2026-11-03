"""Login/sessao contra um PostgreSQL real com o esquema copiado do Supabase.

Roda so com TEST_DATABASE_URL (banco descartavel: as tabelas sao recriadas), ex.:
    docker run -d --rm -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16-alpine
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres pytest tests/test_auth_db.py
"""
import os
import uuid

import bcrypt
import pytest

DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL nao definido")

ADMIN_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
PASSWORD = "senha-antiga-123"


@pytest.fixture(scope="module")
def client():
    import psycopg

    # Mesmo formato do Supabase: bcrypt "$2a$10$..." em auth.users.encrypted_password.
    supabase_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(10, prefix=b"2a")).decode()
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        conn.execute("""
            DROP SCHEMA IF EXISTS auth CASCADE; DROP TABLE IF EXISTS public.admins, public.visits;
            CREATE SCHEMA auth;
            CREATE TABLE auth.users (
                instance_id uuid, id uuid PRIMARY KEY, aud varchar(255), role varchar(255),
                email varchar(255), encrypted_password varchar(255), email_confirmed_at timestamptz,
                last_sign_in_at timestamptz, raw_app_meta_data jsonb, raw_user_meta_data jsonb,
                created_at timestamptz, updated_at timestamptz);
            CREATE UNIQUE INDEX users_email_key ON auth.users (email);
            CREATE TABLE public.admins (user_id uuid PRIMARY KEY REFERENCES auth.users(id));
            CREATE TABLE public.visits (id bigserial PRIMARY KEY, user_id uuid, name text, email text,
                visited_at timestamptz NOT NULL DEFAULT now());
        """)
        conn.execute(
            """INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, raw_user_meta_data, created_at)
               VALUES (%s, 'admin@lcpetro.com', %s, now(), '{"name": "Admin"}', now()),
                      (%s, 'user@lcpetro.com', %s, now(), '{"name": "Usuario"}', now())""",
            (ADMIN_ID, supabase_hash, USER_ID, supabase_hash),
        )
        conn.execute("INSERT INTO public.admins (user_id) VALUES (%s)", (ADMIN_ID,))

    from app.core import config
    config.DATABASE_URL = DB_URL
    config.SECRET_KEY = "test-secret-key"
    config.COOKIE_SECURE = False
    from fastapi.testclient import TestClient
    from app.core.rate_limit import auth_limiter
    from app.main import app
    auth_limiter.max = 10_000  # o limite por IP nao e o assunto destes testes
    with TestClient(app) as c:
        yield c


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_admin_logs_in_with_existing_supabase_password(client):
    r = _login(client, "Admin@LCPetro.com", PASSWORD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"] == {"id": ADMIN_ID, "email": "admin@lcpetro.com", "name": "Admin", "is_admin": True}
    assert "pvbtcalc_session" in r.cookies
    assert "httponly" in r.headers["set-cookie"].lower()


def test_wrong_password_and_unknown_email_rejected(client):
    assert _login(client, "admin@lcpetro.com", "errada").status_code == 401
    assert _login(client, "ninguem@lcpetro.com", PASSWORD).json()["detail"] == "auth.err_invalid_credentials"


def test_bearer_token_and_admin_panel(client):
    token = _login(client, "admin@lcpetro.com", PASSWORD).json()["access_token"]
    client.cookies.clear()
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=h).json()["is_admin"] is True
    assert client.post("/auth/visit", headers=h).status_code == 204
    data = client.get("/admin/overview", headers=h).json()
    assert data["visits"][0]["user_id"] == ADMIN_ID
    assert {u["email"] for u in data["users"]} == {"admin@lcpetro.com", "user@lcpetro.com"}


def test_non_admin_blocked_from_panel(client):
    token = _login(client, "user@lcpetro.com", PASSWORD).json()["access_token"]
    client.cookies.clear()
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=h).json()["is_admin"] is False
    assert client.get("/admin/overview", headers=h).status_code == 403


def test_cookie_session_refresh_and_logout(client):
    _login(client, "admin@lcpetro.com", PASSWORD)
    assert client.get("/auth/me").status_code == 200  # so pelo cookie
    r = client.post("/auth/refresh")
    assert r.status_code == 200 and r.json()["user"]["is_admin"] is True
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_tampered_or_foreign_tokens_rejected(client):
    body = _login(client, "admin@lcpetro.com", PASSWORD).json()
    client.cookies.clear()
    bad = body["access_token"][:-2] + ("AA" if not body["access_token"].endswith("AA") else "BB")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    # refresh token nao serve como access token, e vice-versa
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {body['refresh_token']}"}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": body["access_token"]}).status_code == 401
    assert client.post("/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 200


def test_register_then_login(client):
    client.cookies.clear()
    r = client.post("/auth/register", json={"name": "Novo", "email": "novo@lcpetro.com", "password": "abcdef"})
    assert r.status_code == 200, r.text
    assert r.json()["session"]["user"]["is_admin"] is False
    assert client.post("/auth/register", json={"name": "X", "email": "NOVO@lcpetro.com", "password": "abcdef"}).status_code == 409
    assert _login(client, "novo@lcpetro.com", "abcdef").status_code == 200


def test_calc_routes_require_session(client):
    client.cookies.clear()
    assert client.post("/pvbtpoint", json={}).status_code == 401
    token = _login(client, "user@lcpetro.com", PASSWORD).json()["access_token"]
    client.cookies.clear()
    # com sessao, passa da autenticacao e cai na validacao do corpo
    assert client.post("/pvbtpoint", json={}, headers={"Authorization": f"Bearer {token}"}).status_code == 422
