"""
tests/test_radial_output_mode.py

Fase 9 -- output_mode deixou de ser chumbado em routes/pvbtRadialCurve.py.
Agora sai de RadialCurveMaster.output_mode:

    drainage_radius_ft informado (> 0)  -> "pvbt"
    drainage_radius_ft None / 0 / < 0   -> "volume"

O ramo "volume" nunca tinha executado antes desta fase, apesar de o
frontend (columnsConfig.buildSimulationTable) e a mensagem da UI ja o
anunciarem. Aqui exercitamos os DOIS modos: o master direto e a funcao da
rota (calculate_pvbt_radial e sync e recebe um RadialCurveInput -- da pra
chamar sem HTTP e ainda cobrir a linha exata do return).

    venv/Scripts/python.exe -m pytest tests/test_radial_output_mode.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.routes.pvbtRadialCurve import calculate_pvbt_radial  # noqa: E402
from app.schemas import RadialCurveInput, RadialGeometryInput, RadialCurveOutput  # noqa: E402
from app.services.PVBTfunc import AcidType  # noqa: E402
from app.services.PVBTradialFunc import RadialCurveMaster  # noqa: E402


def _master(drainage_radius_ft):
    return RadialCurveMaster(
        acid_type_cls=AcidType.getAcidTypeByStr("HCl With Inhibitor Corrosion"),
        acid_concentration=0.15,
        rock_type="Indiana Limestone",
        porosity=0.30,
        temperature_k=297.20,
        wellbore_radius_in=6.0,
        payzone_thickness_ft=200.0,
        drainage_radius_ft=drainage_radius_ft,
    )


def _payload(drainage_radius_ft):
    """Mesmo shape que o frontend envia (src/redux/radial/slice.tsx:fetchRadialCurve).
    drainage_radius_ft omitido no dict quando None -- reproduz o `?? null` do
    front virando ausencia de campo apos JSON.stringify."""
    geometry = {"wellbore_radius_in": 6.0, "payzone_thickness_ft": 200.0}
    if drainage_radius_ft is not None:
        geometry["drainage_radius_ft"] = drainage_radius_ft
    return {
        "system": {
            "rock_type": "Indiana Limestone",
        "porosity": 0.30,
        "acid_system": "HCl With Inhibitor Corrosion",
        "acid_concentration": 0.15,
        "temperature_k": 297.20,
        },
        "geometry": geometry,
        "radial_targets": {"target_mode": "length", "targets": [5.0, 20.0]},
        "flowrate_sweep": {"min": 0.1, "max": 5.0, "steps": 8},
    }


def test_schema_drainage_radius_optional_and_defaulted():
    g = RadialGeometryInput(wellbore_radius_in=6.0, payzone_thickness_ft=200.0)
    assert g.drainage_radius_ft is None

    g2 = RadialGeometryInput(wellbore_radius_in=6.0, payzone_thickness_ft=200.0, drainage_radius_ft=1500.0)
    assert g2.drainage_radius_ft == 1500.0

    parsed = RadialCurveInput(**_payload(1500.0))
    assert parsed.geometry.drainage_radius_ft == 1500.0
    assert RadialCurveInput(**_payload(None)).geometry.drainage_radius_ft is None


def test_output_mode_pvbt_when_drainage_radius_set():
    assert _master(1500.0).output_mode == "pvbt"
    assert _master(1e-3).output_mode == "pvbt"


def test_output_mode_volume_when_no_drainage_radius():
    assert _master(None).output_mode == "volume"
    assert _master(0.0).output_mode == "volume"
    assert _master(-10.0).output_mode == "volume"


def test_route_returns_volume_without_drainage_radius():
    result = calculate_pvbt_radial(RadialCurveInput(**_payload(None)))
    assert result["output_mode"] == "volume"
    RadialCurveOutput(**result)
    assert len(result["curves"]) == 2
    assert result["curves"][0]["acidvolumepoints"] is not None


def test_route_returns_pvbt_with_drainage_radius():
    result = calculate_pvbt_radial(RadialCurveInput(**_payload(1500.0)))
    assert result["output_mode"] == "pvbt"
    RadialCurveOutput(**result)
    assert len(result["curves"]) == 2


def test_only_output_mode_changes_between_the_two_runs():
    """Mesma geometria fora o raio de drenagem -> as curvas numericas sao
    identicas; so output_mode difere. (drainage_radius nao entra no modelo
    fechado -- ver docstring de RadialGeometry.)"""
    vol = calculate_pvbt_radial(RadialCurveInput(**_payload(None)))
    pvbt = calculate_pvbt_radial(RadialCurveInput(**_payload(1500.0)))
    assert (vol["output_mode"], pvbt["output_mode"]) == ("volume", "pvbt")
    assert vol["curves"][0]["pvbtpoints"] == pvbt["curves"][0]["pvbtpoints"]
    assert vol["curves"][0]["acidvolumepoints"] == pvbt["curves"][0]["acidvolumepoints"]


if __name__ == "__main__":
    test_schema_drainage_radius_optional_and_defaulted()
    test_output_mode_pvbt_when_drainage_radius_set()
    test_output_mode_volume_when_no_drainage_radius()
    test_route_returns_volume_without_drainage_radius()
    test_route_returns_pvbt_with_drainage_radius()
    test_only_output_mode_changes_between_the_two_runs()
    print("OK -- output_mode dinamico verificado nos dois modos.")
