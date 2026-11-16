"""Simulacoes salvas no banco (ate 10 por conta). Requer TEST_DATABASE_URL (banco descartavel)."""
import os
import uuid

import pytest

DB_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="TEST_DATABASE_URL nao definido")


@pytest.fixture(scope="module")
def client():
    import psycopg

    with psycopg.connect(DB_URL, autocommit=True) as conn:
        conn.execute("""
            DROP SCHEMA IF EXISTS auth CASCADE;
            DROP TABLE IF EXISTS public.admins, public.visits, public.user_onboarding, public.saved_simulations;
            CREATE SCHEMA auth;
            CREATE TABLE auth.users (id uuid PRIMARY KEY, email text, encrypted_password text);
            CREATE TABLE public.admins (user_id uuid PRIMARY KEY);
            CREATE TABLE public.visits (id bigserial PRIMARY KEY, user_id uuid, name text, email text,
                visited_at timestamptz NOT NULL DEFAULT now());
        """)
    from app.core import config, db_gateway, simulations_store
    db_gateway._users_cols = None
    db_gateway._onboarding_ready = False
    db_gateway._cache.clear()
    simulations_store._ready = False
    config.DATABASE_URL = DB_URL
    config.SECRET_KEY = "test-secret-key"
    config.COOKIE_SECURE = False
    from fastapi.testclient import TestClient
    from app.core.rate_limit import api_limiter, auth_limiter
    from app.main import app
    auth_limiter.max = api_limiter.max = 10_000
    with TestClient(app) as c:
        yield c


def _user(client):
    r = client.post("/auth/register", json={"name": "U", "email": f"{uuid.uuid4().hex[:8]}@t.local", "password": "abcdef"})
    client.cookies.clear()
    return {"Authorization": f"Bearer {r.json()['session']['access_token']}"}


def _save(client, h, sim_id, **patch):
    return client.put(f"/me/simulations/{sim_id}", headers=h, json={"flowRegime": "linear", **patch})


def test_requires_session(client):
    client.cookies.clear()
    assert client.get("/me/simulations").status_code == 401
    assert client.put("/me/simulations/x", json={"flowRegime": "linear"}).status_code == 401


def test_merge_rename_get_delete(client):
    h = _user(client)
    assert _save(client, h, "HCl/25C", rock="Indiana Limestone", curves=[{"id": "HCl/25C", "pvbtPoints": [1, 2]}]).json() == {"evicted": []}
    # parte radial chega depois: nao apaga as curvas ja salvas
    assert _save(client, h, "HCl/25C", designSeries=[{"temperature_k": 300}]).status_code == 200
    full = client.get("/me/simulations/HCl/25C", headers=h).json()
    assert full["curves"][0]["pvbtPoints"] == [1, 2] and full["designSeries"] == [{"temperature_k": 300}]
    assert full["rock"] == "Indiana Limestone" and full["schemaVersion"] == 1 and full["id"] == "HCl/25C"
    lst = client.get("/me/simulations", headers=h).json()
    assert lst["max"] == 10 and "curves" not in lst["items"][0] and lst["items"][0]["label"] == "HCl/25C"
    assert client.patch("/me/simulations/HCl/25C", headers=h, json={"label": "Ensaio 1"}).status_code == 204
    assert client.get("/me/simulations", headers=h).json()["items"][0]["label"] == "Ensaio 1"
    assert client.delete("/me/simulations/HCl/25C", headers=h).status_code == 204
    assert client.get("/me/simulations/HCl/25C", headers=h).status_code == 404
    assert _save(client, h, "x", flowRegime="other").status_code == 422


def test_limit_ten_evicts_oldest_and_users_are_isolated(client):
    h1, h2 = _user(client), _user(client)
    for i in range(10):
        assert _save(client, h1, f"s{i}").json()["evicted"] == []
    _save(client, h1, "s0", rock="atualizada")  # s0 passa a ser a mais recente
    r = _save(client, h1, "s10")
    assert r.json()["evicted"] == [{"id": "s1", "label": "s1"}]
    ids = [x["id"] for x in client.get("/me/simulations", headers=h1).json()["items"]]
    assert len(ids) == 10 and ids[0] == "s10" and "s1" not in ids and "s0" in ids
    # outro usuario nao ve nem apaga nada do primeiro
    assert client.get("/me/simulations", headers=h2).json()["items"] == []
    assert client.get("/me/simulations/s0", headers=h2).status_code == 404
    assert client.delete("/me/simulations", headers=h2).status_code == 204
    assert len(client.get("/me/simulations", headers=h1).json()["items"]) == 10
    assert client.delete("/me/simulations", headers=h1).status_code == 204
    assert client.get("/me/simulations", headers=h1).json()["items"] == []
