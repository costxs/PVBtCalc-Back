from fastapi import FastAPI
from app.routes import pvbtPoint, pvbtCurve, getParameters, auth
from app.dependencies import setup_middlewares
app = FastAPI(title="Meu Projeto FastAPI")
setup_middlewares(app)
app.include_router(auth.router)
app.include_router(pvbtPoint.router)
app.include_router(pvbtCurve.router)
app.include_router(getParameters.router)

@app.get("/")
def home():
    return {"message": "API FastAPI rodando!"}
