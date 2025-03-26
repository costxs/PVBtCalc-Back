from app.services.PVBTfunc import AcidType, PVBtMaster
from app.schemas import PVBtInputPoint, AnalicalInput
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


def get_correct_param(data: AnalicalInput):

    match data.analitical_param:
        case 'temperature':
                master = PVBtMaster(
                    acidtype=AcidType.getAcidTypeByStr(data.acid_type),
                    acid_concentration=data.acid_concentration,
                    core_diameter=data.core_diameter,
                    core_length=data.core_length,
                    core_porosity=data.core_porosity,
                    rock_type=data.rock_type,
                    temperature=data.temperature,
                    flowrate=data.flowrate,
                    minimun_temperature=data.minimum_analitical,
                    step_numbers=data.step_numbers,
                )
                pvbt, temperature, velocity, ida, volumetobt, timetobt, wormhole, darcy = master.PVBtCurveAnaliticalWhiteDetailsTemp()
                return {
                    "analyzed":"temperature",
                    "pvbtpoints": pvbt, 
                    "analiticalpoints": temperature,
                    "insterticialvelocity":velocity,
                    "ida":ida,
                    "volumetobt":volumetobt,
                    "timetobt":timetobt,
                    "wormholevelocity":wormhole,
                    "darcyvelocity":darcy
                    }

        case 'core length':
                master = PVBtMaster(
                    acidtype=AcidType.getAcidTypeByStr(data.acid_type),
                    acid_concentration=data.acid_concentration,
                    core_diameter=data.core_diameter,
                    core_length=data.core_length,
                    core_porosity=data.core_porosity,
                    rock_type=data.rock_type,
                    temperature=data.temperature,
                    flowrate=data.flowrate,
                    mininum_length=data.minimum_analitical,
                    step_numbers=data.step_numbers,
                )
                pvbt, analitical, velocity, ida, volumetobt, timetobt, wormhole, darcy = master.PVBtCurveAnaliticalWhiteDetailsLength()
                return {
                    "analyzed":"Length",
                    "pvbtpoints": pvbt, 
                    "analiticalpoints": analitical,
                    "insterticialvelocity":velocity,
                    "ida":ida,
                    "volumetobt":volumetobt,
                    "timetobt":timetobt,
                    "wormholevelocity":wormhole,
                    "darcyvelocity":darcy
                    }
        case 'core porosity':
                master = PVBtMaster(
                    acidtype=AcidType.getAcidTypeByStr(data.acid_type),
                    acid_concentration=data.acid_concentration,
                    core_diameter=data.core_diameter,
                    core_length=data.core_length,
                    core_porosity=data.core_porosity,
                    rock_type=data.rock_type,
                    temperature=data.temperature,
                    flowrate=data.flowrate,
                    minimum_porosity=data.minimum_analitical,
                    step_numbers=data.step_numbers,
                )
                pvbt, analitical, velocity, ida, volumetobt, timetobt, wormhole, darcy = master.PVBtCurveAnaliticalWhiteDetailsPhi()
                return {
                    "analyzed":"Porosity",
                    "pvbtpoints": pvbt, 
                    "analiticalpoints": analitical,
                    "insterticialvelocity":velocity,
                    "ida":ida,
                    "volumetobt":volumetobt,
                    "timetobt":timetobt,
                    "wormholevelocity":wormhole,
                    "darcyvelocity":darcy
                    }
        case 'core diameter':
                master = PVBtMaster(
                    acidtype=AcidType.getAcidTypeByStr(data.acid_type),
                    acid_concentration=data.acid_concentration,
                    core_diameter=data.core_diameter,
                    core_length=data.core_length,
                    core_porosity=data.core_porosity,
                    rock_type=data.rock_type,
                    temperature=data.temperature,
                    flowrate=data.flowrate,
                    minimum_diameter=data.minimum_analitical,
                    step_numbers=data.step_numbers,
                )
                pvbt, analitical, velocity, ida, volumetobt, timetobt, wormhole, darcy = master.PVBtCurveAnaliticalWhiteDetailsLength()
                return {
                    "analyzed":"Diameter",
                    "pvbtpoints": pvbt, 
                    "analiticalpoints": analitical,
                    "insterticialvelocity":velocity,
                    "ida":ida,
                    "volumetobt":volumetobt,
                    "timetobt":timetobt,
                    "wormholevelocity":wormhole,
                    "darcyvelocity":darcy
                    }
        case 'acid concentration':
                master = PVBtMaster(
                    acidtype=AcidType.getAcidTypeByStr(data.acid_type),
                    acid_concentration=data.acid_concentration,
                    core_diameter=data.core_diameter,
                    core_length=data.core_length,
                    core_porosity=data.core_porosity,
                    rock_type=data.rock_type,
                    temperature=data.temperature,
                    flowrate=data.flowrate,
                    minimum_concentration=data.minimum_analitical,
                    step_numbers=data.step_numbers,
                )
                pvbt, analitical, velocity, ida, volumetobt, timetobt, wormhole, darcy = master.PVBtCurveAnaliticalWhiteDetailsConcentration()
                return {
                    "analyzed":"Acid Concentration",
                    "pvbtpoints": pvbt, 
                    "analiticalpoints": analitical,
                    "insterticialvelocity":velocity,
                    "ida":ida,
                    "volumetobt":volumetobt,
                    "timetobt":timetobt,
                    "wormholevelocity":wormhole,
                    "darcyvelocity":darcy
                    }
