from fastapi import APIRouter, Depends
from app.schemas import PVBtInputCurve, PVBtOutputCurveWhithDetails
from app.services.PVBTfunc import AcidType, PVBtMaster
from app.services.linear_validity import linear_validity_window
from app.core.security import get_current_user
router = APIRouter()

@router.post("/pvbtcurve", response_model=PVBtOutputCurveWhithDetails)
def calculate_pvbt(data: PVBtInputCurve):
    master = PVBtMaster(
        acidtype=AcidType.getAcidTypeByStr(data.acid_type),
        acid_concentration=data.acid_concentration,
        core_diameter=data.core_diameter,
        core_length=data.core_length,
        core_porosity=data.core_porosity,
        rock_type=data.rock_type,
        temperature=data.temperature,
        flowrate=data.flowrate,
        minimun_flowrate=data.minimum_flowrate,
        step_numbers=data.step_numbers,
    )
    pvbt, flowrates, velocity, ida, volumetobt, timetobt, wormhole, darcy, status = master.PVBtCurveCalculatorWhiteDetails()

    setup = master.getSetup()
    within_validity_range, validity_metadata = linear_validity_window(
        flowrates,
        a=setup.acidsetup.a,
        b=setup.acidsetup.b,
        n=setup.acidsetup.n,
        keff=setup.acidsetup.k0 * setup.difisioncoefficient,
        A_o=setup.injectionfacecross,
        lc=setup.core_geometry.dimensionless_length,
        phi=setup.core_geometry.core_porosity,
        C_Ao=setup.acidsetup.acid_concentration,
        X=setup.acid_volumetric_dissolving_power100,
    )

    if validity_metadata is not None:
        point = PVBtMaster(
            acidtype=AcidType.getAcidTypeByStr(data.acid_type),
            acid_concentration=data.acid_concentration,
            core_diameter=data.core_diameter,
            core_length=data.core_length,
            core_porosity=data.core_porosity,
            rock_type=data.rock_type,
            temperature=data.temperature,
            flowrate=validity_metadata["q_opt_cm3_min"],
        ).PVBtPointCalculator()
        if point is not None:
            validity_metadata["pvbt_at_q_opt"] = point

    return {
        "pvbtpoints": pvbt,
        "flowratepoints": flowrates,
        "insterticialvelocity":velocity,
        "ida":ida,
        "volumetobt":volumetobt,
        "timetobt":timetobt,
        "wormholevelocity":wormhole,
        "darcyvelocity":darcy,
        "status": status,
        "within_validity_range": within_validity_range,
        "metadata": validity_metadata,
        }
