import os


def _csv(name: str, default: str) -> list[str]:
    return [v.strip().rstrip("/") for v in os.environ.get(name, default).split(",") if v.strip()]


# Banco PostgreSQL (contas em auth.users, public.admins, public.visits). So este
# backend acessa o banco; a URL vive apenas em variavel de ambiente.
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "5"))

# Chave que assina os tokens e o cookie de sessao. Trocar a chave desloga todos.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
ACCESS_TOKEN_TTL = int(os.environ.get("ACCESS_TOKEN_TTL", "3600"))  # segundos
SESSION_TTL = int(os.environ.get("SESSION_TTL", str(30 * 24 * 3600)))  # segundos
SESSION_COOKIE = "pvbtcalc_session"
# Cookie so via HTTPS em producao; COOKIE_SECURE=false para testar em http://localhost.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() not in ("0", "false", "no")

# A origem de producao do frontend e sempre permitida; ALLOWED_ORIGINS acrescenta outras.
PRODUCTION_ORIGIN = "https://pv-bt-calc.vercel.app"
ALLOWED_ORIGINS = list(dict.fromkeys(
    [PRODUCTION_ORIGIN] + _csv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
))

# Atras de proxy (Render, etc.) o IP real vem em X-Forwarded-For.
TRUST_PROXY = os.environ.get("TRUST_PROXY", "").lower() in ("1", "true", "yes")

# Limite de tentativas por IP nas rotas /auth: (max requisicoes, janela em segundos).
AUTH_RATE_LIMIT = (int(os.environ.get("AUTH_RATE_MAX", "10")), int(os.environ.get("AUTH_RATE_WINDOW", "60")))
# Limite geral por IP nas rotas de calculo/exportacao.
API_RATE_LIMIT = (int(os.environ.get("API_RATE_MAX", "120")), int(os.environ.get("API_RATE_WINDOW", "60")))

MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(20 * 1024 * 1024)))
