from app.services.PVBTfunc import AcidType, PVBtMaster
from app.schemas import PVBtInputPoint
from typing import List
def getparam(data: PVBtInputPoint):

    master = PVBtMaster(
        AcidType.getAcidTypeByStr(data.acid_type),
        data.acid_concentration,
        data.core_diameter,
        data.core_length,
        data.core_porosity,
        data.rock_type,
        data.temperature,
        data.flowrate
    )

    setup = master.getSetup()

    return{
        "ro":setup.acid_density,
        "X":setup.acid_volumetric_dissolving_power100,
        "x":setup.acid_volumetric_dissolving_power,
        "n":setup.acidsetup.n,
        "a":setup.acidsetup.a,
        "b":setup.acidsetup.b,
        "k0":setup.acidsetup.k0,
    }

def getOptPVBt(PVBt:List[float]):
    return min(PVBt)