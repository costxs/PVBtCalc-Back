from fastapi import APIRouter
from app.schemas import SkinEvolutionInput
from app.services.tools import generate_skin_evolution

router = APIRouter(prefix="/skinevolution", tags=["Skin Evolution"])

@router.post("/")
async def calc_skin_evolution(data: SkinEvolutionInput):
    print(f"SkinEvolution request: Temp={data.temperature_k}, Flowrates={data.flowrates_to_compare}")
    resultados = generate_skin_evolution(data, data.flowrates_to_compare)
    return resultados
