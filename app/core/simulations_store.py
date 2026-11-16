"""Simulacoes salvas por usuario (public.saved_simulations), no maximo MAX_SAVED por conta.

Cada linha guarda o snapshot completo que o frontend monta (curvas, Design Plot, Skin).
O frontend manda so o que mudou; a juncao com o que ja esta salvo e feita aqui, dentro
de uma transacao, para duas gravacoes simultaneas da mesma simulacao nao se apagarem.
Ao passar do limite, as mais antigas (pela data da ultima gravacao) saem e a resposta
diz quais foram, para a tela avisar.
"""
import json
import time

from psycopg.types.json import Jsonb

from app.core.db_gateway import GatewayError, _get_pool

MAX_SAVED = 10
SCHEMA_VERSION = 1
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
HEAVY_KEYS = ("curves", "designSeries", "skinSeries")

_ready = False


def _fail(e: Exception) -> GatewayError:
    if isinstance(e, GatewayError):
        return e
    import traceback
    traceback.print_exc()
    return GatewayError(503, "auth.err_server_unavailable")


def ensure_table() -> None:
    global _ready
    if _ready:
        return
    try:
        with _get_pool().connection(timeout=10) as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS public.saved_simulations (
                       user_id text NOT NULL,
                       sim_id text NOT NULL,
                       payload jsonb NOT NULL,
                       saved_at timestamptz NOT NULL DEFAULT now(),
                       PRIMARY KEY (user_id, sim_id))"""
            )
        _ready = True
    except Exception as e:
        raise _fail(e)


def _empty(sim_id: str, flow_regime: str, now_ms: int) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION, "id": sim_id, "label": sim_id, "flowRegime": flow_regime,
        "createdAt": now_ms, "savedAt": now_ms, "rock": "", "acid": "", "porosity": None,
        "concentration": None, "temperature": None, "targets": [], "curves": [],
        "designSeries": None, "skinSeries": None,
    }


def upsert(user_id: str, sim_id: str, patch: dict) -> list[dict]:
    """Junta `patch` ao snapshot salvo (ou cria) e aplica o limite. Devolve as removidas."""
    ensure_table()
    now_ms = int(time.time() * 1000)
    try:
        with _get_pool().connection(timeout=10) as conn:
            with conn.transaction():
                row = conn.execute(
                    "SELECT payload FROM public.saved_simulations WHERE user_id = %s AND sim_id = %s FOR UPDATE",
                    (user_id, sim_id),
                ).fetchone()
                base = row["payload"] if row else _empty(sim_id, patch["flowRegime"], now_ms)
                merged = {**base, **{k: v for k, v in patch.items() if v is not None}}
                merged.update({
                    "schemaVersion": SCHEMA_VERSION, "id": sim_id, "flowRegime": patch["flowRegime"],
                    "createdAt": base.get("createdAt", now_ms), "savedAt": now_ms,
                })
                if len(json.dumps(merged)) > MAX_SNAPSHOT_BYTES:
                    raise GatewayError(413, "sim.err_too_large")
                conn.execute(
                    """INSERT INTO public.saved_simulations (user_id, sim_id, payload, saved_at)
                       VALUES (%s, %s, %s, now())
                       ON CONFLICT (user_id, sim_id) DO UPDATE SET payload = EXCLUDED.payload, saved_at = now()""",
                    (user_id, sim_id, Jsonb(merged)),
                )
                evicted = conn.execute(
                    """DELETE FROM public.saved_simulations
                       WHERE user_id = %s AND sim_id IN (
                           SELECT sim_id FROM public.saved_simulations WHERE user_id = %s
                           ORDER BY saved_at DESC OFFSET %s)
                       RETURNING sim_id, payload->>'label' AS label""",
                    (user_id, user_id, MAX_SAVED),
                ).fetchall()
        return [{"id": r["sim_id"], "label": r["label"] or r["sim_id"]} for r in evicted]
    except Exception as e:
        raise _fail(e)


def _run(sql: str, params: tuple, fetch: str = "all"):
    ensure_table()
    try:
        with _get_pool().connection(timeout=10) as conn:
            cur = conn.execute(sql, params)
            if fetch == "all":
                return cur.fetchall()
            if fetch == "one":
                return cur.fetchone()
            return cur.rowcount
    except Exception as e:
        raise _fail(e)


def list_summaries(user_id: str) -> list[dict]:
    rows = _run(
        f"""SELECT payload - '{HEAVY_KEYS[0]}' - '{HEAVY_KEYS[1]}' - '{HEAVY_KEYS[2]}' AS summary
            FROM public.saved_simulations WHERE user_id = %s ORDER BY saved_at DESC""",
        (user_id,),
    )
    return [r["summary"] for r in rows]


def get(user_id: str, sim_id: str) -> dict | None:
    row = _run(
        "SELECT payload FROM public.saved_simulations WHERE user_id = %s AND sim_id = %s",
        (user_id, sim_id), fetch="one",
    )
    return row["payload"] if row else None


def rename(user_id: str, sim_id: str, label: str) -> bool:
    n = _run(
        """UPDATE public.saved_simulations SET payload = jsonb_set(payload, '{label}', to_jsonb(%s::text))
           WHERE user_id = %s AND sim_id = %s""",
        (label, user_id, sim_id), fetch="count",
    )
    return n > 0


def delete(user_id: str, sim_id: str) -> None:
    _run("DELETE FROM public.saved_simulations WHERE user_id = %s AND sim_id = %s", (user_id, sim_id), fetch="count")


def delete_all(user_id: str) -> None:
    _run("DELETE FROM public.saved_simulations WHERE user_id = %s", (user_id,), fetch="count")
