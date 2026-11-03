"""Mesmo login, mas com uma copia minima de auth.users (sem email_confirmed_at,
metadados, datas...): so id, email e encrypted_password. Requer TEST_DATABASE_URL."""
import os
import uuid

import bcrypt
import pytest

DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL nao definido")

ADMIN_ID = str(uuid.uuid4())
PASSWORD = "senha-antiga-123"


@pytest.fixture(scope="module")
def client():
    import psycopg

    hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(10, prefix=b"2a")).decode()
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        conn.execute("""
            DROP SCHEMA IF EXISTS auth CASCADE; DROP TABLE IF EXISTS public.admins, public.visits;
            CREATE SCHEMA auth;
            CREATE TABLE auth.users (id uuid PRIMARY KEY, email text, encrypted_password text);
            CREATE TABLE public.admins (user_id uuid PRIMARY KEY);
            CREATE TABLE public.visits (id bigserial PRIMARY KEY, user_id uuid, name text, email text,
                visited_at timestamptz NOT NULL DEFAULT now());
        """)
        conn.execute("INSERT INTO auth.users VALUES (%s, 'admin@lcpetro.com', %s)", (ADMIN_ID, hashed))
        conn.execute("INSERT INTO public.admins VALUES (%s)", (ADMIN_ID,))

    from app.core import config, db_gateway
    db_gateway._users_cols = None
    db_gateway._cache.clear()
    config.DATABASE_URL = DB_URL
    config.SECRET_KEY = "test-secret-key"
    config.COOKIE_SECURE = False
    from fastapi.testclient import TestClient
    from app.core.rate_limit import auth_limiter
    from app.main import app
    auth_limiter.max = 10_000
    with TestClient(app) as c:
        yield c


def test_login_admin_panel_and_register_with_minimal_table(client):
    r = client.post("/auth/login", json={"email": "admin@lcpetro.com", "password": PASSWORD})
    assert r.status_code == 200, r.text
    assert r.json()["user"] == {"id": ADMIN_ID, "email": "admin@lcpetro.com", "name": "admin@lcpetro.com", "is_admin": True}
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/auth/visit", headers=h).status_code == 204
    users = client.get("/admin/overview", headers=h).json()["users"]
    assert users[0]["email"] == "admin@lcpetro.com" and users[0]["created_at"] is None
    assert client.post("/auth/login", json={"email": "admin@lcpetro.com", "password": "x"}).status_code == 401
    r = client.post("/auth/register", json={"name": "Novo", "email": "novo@lcpetro.com", "password": "abcdef"})
    assert r.status_code == 200, r.text
    assert client.post("/auth/login", json={"email": "novo@lcpetro.com", "password": "abcdef"}).status_code == 200
