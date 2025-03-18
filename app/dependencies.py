from fastapi.middleware.cors import CORSMiddleware

def setup_middlewares(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Permitir todas as origens (apenas para desenvolvimento)
        allow_credentials=True,
        allow_methods=["*"],  # Permitir todos os métodos
        allow_headers=["*"],  # Permitir todos os headers
    )
