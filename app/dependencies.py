import traceback

from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


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


def setup_middlewares(app):
    # add_middleware empilha de fora pra dentro na ordem INVERSA de adicao:
    # o ultimo adicionado fica mais externo. Adiciona-se o catch-all primeiro
    # e o CORS depois, para que o CORS envolva o catch-all e adicione os
    # headers tambem nas respostas de erro.
    app.middleware("http")(_catch_all_errors)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Permitir todas as origens (apenas para desenvolvimento)
        allow_credentials=True,
        allow_methods=["*"],  # Permitir todos os métodos
        allow_headers=["*"],  # Permitir todos os headers
    )
