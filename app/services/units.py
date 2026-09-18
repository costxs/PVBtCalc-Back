"""
services/units.py

Conversao de vazao entre a unidade que a UI coleta e o SI (m3/s) que os
modelos usam internamente.

Duas escalas, duas unidades de entrada:
  - linear (escala de core):  cm3/min  -- src/components/InletPressure.tsx
  - radial (escala de campo): bbl/min  -- src/components/SimuCard.tsx:283

O modelo linear (services/PVBTfunc.py:ConvertUnits) faz a propria conversao
inline e NAO passa por aqui -- decisao deliberada de nao tocar no caminho ja
validado. Este modulo existe para o caminho radial, que antes aplicava por
engano o fator de cm3/min sobre um numero em bbl/min (q_o ~1.59e5x menor,
K estourando exp() e status "clipped" em vazoes normais).
"""

CM3_MIN_TO_M3S = 1e-6 / 60.0        # 1 cm^3/min -> m^3/s
BBL_TO_M3 = 0.158987294928         # 1 oil barrel (42 US gal) em m^3
BBL_MIN_TO_M3S = BBL_TO_M3 / 60.0  # 1 bbl/min -> m^3/s

_TO_M3S = {
    "cm3_min": CM3_MIN_TO_M3S,
    "bbl_min": BBL_MIN_TO_M3S,
}


def _factor(unit):
    try:
        return _TO_M3S[unit]
    except KeyError:
        raise ValueError(
            f"unidade de vazao desconhecida: {unit!r} (esperado {sorted(_TO_M3S)})"
        ) from None


def flowrate_to_m3s(value, unit):
    """Converte `value` na unidade `unit` ("cm3_min" | "bbl_min") para m3/s."""
    return value * _factor(unit)


def m3s_to_flowrate(value, unit):
    """Inverso de flowrate_to_m3s: m3/s -> unidade `unit`."""
    return value / _factor(unit)


BBL_TO_GAL = 42.0  # 1 oil barrel = 42 US gal, EXATO (nao passa por m3)


def flowrate_to_display(value_bbl_min, payzone_thickness_ft):
    """bbl/min -> gal/(ft.min) -- SO usado pelo caminho RADIAL (Fase 8).

    O artigo (Figs. 27+) normaliza vazao por pe de zona; bbl/min (escala de
    campo, sem essa normalizacao) nao e comparavel entre pocos de espessura
    diferente. O linear nao tem equivalente -- gal/(ft.min) nao tem sentido
    em escala de core (cm3/min) -- entao esta funcao nunca e chamada por
    aquele caminho.

    Multiplica por 42 (bbl->gal) direto, sem passar por m3/s: BBL_TO_M3 e
    definido a partir dos mesmos 42 gal exatos, entao ir bbl->m3->gal so
    reintroduziria o arredondamento de "gal por m3" sem necessidade.
    """
    return (value_bbl_min * BBL_TO_GAL) / payzone_thickness_ft
