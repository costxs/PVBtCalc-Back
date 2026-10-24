from fastapi import Depends, FastAPI
from app.routes import pvbtPoint, pvbtCurve, getParameters, auth, optAnalitical, pvbtRadialCurve, skinEvolution, designPlot, exportRadial, exportLinear, optRadial, admin
from app.dependencies import setup_middlewares
from app.core.security import get_current_user
from app.core.rate_limit import api_limiter
app = FastAPI(title="Meu Projeto FastAPI", docs_url=None, redoc_url=None, openapi_url=None)
setup_middlewares(app)
# Toda rota de calculo/exportacao exige sessao valida + limite de requisicoes por IP.
PROTECTED = [Depends(api_limiter), Depends(get_current_user)]
app.include_router(auth.router)
app.include_router(pvbtPoint.router, dependencies=PROTECTED)
app.include_router(pvbtCurve.router, dependencies=PROTECTED)
app.include_router(getParameters.router, dependencies=PROTECTED)
app.include_router(optAnalitical.router, dependencies=PROTECTED)
app.include_router(pvbtRadialCurve.router, dependencies=PROTECTED)
app.include_router(skinEvolution.router, dependencies=PROTECTED)
app.include_router(designPlot.router, dependencies=PROTECTED)
app.include_router(exportRadial.router, dependencies=PROTECTED)
app.include_router(exportLinear.router, dependencies=PROTECTED)
app.include_router(optRadial.router, dependencies=PROTECTED)
app.include_router(admin.router, dependencies=[Depends(api_limiter)])

@app.get("/")
def home():
    return {"message": "API FastAPI rodando!"}
