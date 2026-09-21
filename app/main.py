from fastapi import FastAPI
from app.routes import pvbtPoint, pvbtCurve, getParameters, auth, optAnalitical, pvbtRadialCurve, skinEvolution, designPlot, exportRadial, exportLinear, optRadial
from app.dependencies import setup_middlewares
app = FastAPI(title="Meu Projeto FastAPI")
setup_middlewares(app)
app.include_router(auth.router)
app.include_router(pvbtPoint.router)
app.include_router(pvbtCurve.router)
app.include_router(getParameters.router)
app.include_router(optAnalitical.router)
app.include_router(pvbtRadialCurve.router)
app.include_router(skinEvolution.router)
app.include_router(designPlot.router)
app.include_router(exportRadial.router)
app.include_router(exportLinear.router)
app.include_router(optRadial.router)

@app.get("/")
def home():
    return {"message": "API FastAPI rodando!"}
