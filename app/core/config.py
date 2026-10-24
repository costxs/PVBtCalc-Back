import os


def _csv(name: str, default: str) -> list[str]:
    return [v.strip().rstrip("/") for v in os.environ.get(name, default).split(",") if v.strip()]


# O banco (Supabase) so e acessado a partir deste backend. As chaves vivem apenas
# aqui (variaveis de ambiente) e nunca sao enviadas ao browser.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
# Chave publicavel: usada somente para repassar login/cadastro ao Supabase Auth.
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
# Chave de servico (ignora RLS): usada somente para gravar a tabela `visits`.
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

ALLOWED_ORIGINS = _csv("ALLOWED_ORIGINS", "https://pv-bt-calc.vercel.app,http://localhost:5173,http://127.0.0.1:5173")

# Atras de proxy (Render, etc.) o IP real vem em X-Forwarded-For.
TRUST_PROXY = os.environ.get("TRUST_PROXY", "").lower() in ("1", "true", "yes")

# Limite de tentativas por IP nas rotas /auth: (max requisicoes, janela em segundos).
AUTH_RATE_LIMIT = (int(os.environ.get("AUTH_RATE_MAX", "10")), int(os.environ.get("AUTH_RATE_WINDOW", "60")))
# Limite geral por IP nas rotas de calculo/exportacao.
API_RATE_LIMIT = (int(os.environ.get("API_RATE_MAX", "120")), int(os.environ.get("API_RATE_WINDOW", "60")))

MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(20 * 1024 * 1024)))
