from pydantic import BaseModel
from typing import List
class PVBtInputPoint(BaseModel):
    acid_type: str
    acid_concentration: float
    core_diameter: float
    core_length: float
    core_porosity: float
    rock_type: str
    temperature: float
    flowrate: float

class PVBtInputCurve(BaseModel):
    acid_type: str
    acid_concentration: float
    core_diameter: float
    core_length: float
    core_porosity: float
    rock_type: str
    temperature: float
    flowrate: float
    minimum_flowrate: float
    step_numbers: int

class PVBtOutputPoint(BaseModel):
    pore_volume_to_breakthrough: float

class PVBtOutputCurveWhithDetails(BaseModel):
    pvbtpoints: List[float]
    flowratepoints: List[float]
    insterticialvelocity: List[float]
    ida: List[float]
    volumetobt: List[float]
    timetobt: List[float]
    wormholevelocity: List[float]
    darcyvelocity: List[float]

class PVBtOutputPointWhithDetails(BaseModel):
    PVBtPoints: float
    FlowratePoints: float
    intersticialVelocity: float
    iDa: float
    volumeToBt: float
    timeToBt: float
    wormholeVelocity: float
    darcyVelocity: float


class PVBtOutputCurve(BaseModel):
    PVBtPoints: List[float]
    FlowratePoints: List[float]