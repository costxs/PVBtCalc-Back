import traceback

from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core import config


async def _catch_all_errors(request: Request, call_next):
    """Converte qualquer excecao nao tratada (incl. ResponseValidationError,
    que o FastAPI nao captura) numa resposta 500 JSON normal.

    Sem isto, essas excecoes sobem ate o ServerErrorMiddleware do Starlette,
    que fica POR FORA do CORSMiddleware -- a resposta 500 sai sem o header
    Access-Control-Allow-Origin e o browser reporta como erro de CORS,
    escondendo o erro real. Este middleware roda por DENTRO do CORS (ver
    ordem de add_middleware em setup_middlewares), entao o 500 que ele
    devolve recebe os headers de CORS normalmente.
    """
    try:
        return await call_next(request)
    except Exception:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": "internal server error -- ver traceback no log do servidor"},
        )


async def _security_layer(request: Request, call_next):
    """Limita o tamanho do corpo e acrescenta cabecalhos de seguranca a toda resposta."""
    try:
        too_big = int(request.headers.get("content-length", "0")) > config.MAX_BODY_BYTES
    except ValueError:
        too_big = True
    if too_big:
        return JSONResponse(status_code=413, content={"detail": "payload too large"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/auth"):
        response.headers["Cache-Control"] = "no-store"
    return response


def setup_middlewares(app):
    app.middleware("http")(_catch_all_errors)
    app.middleware("http")(_security_layer)

    # Autenticacao e por Bearer token (sem cookies): nao ha credenciais de navegador a proteger.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )
