"""
export_workbook_linear.py
------------------------------------------------------------------
Workbook .xlsx do regime LINEAR (XlsxWriter) -- irmao de export_workbook.py
(radial), reusando dele tudo o que nao depende de regime (formatos, titulo/
imagem escalada, nomes de aba, formato numerico) e de export_plots.py a
figura (mesma build_simulation_figure, agora parametrizada por rotulo/escala).

Nenhum calculo fisico aqui. q_opt e a janela vem de curve.metadata -- o MESMO
objeto que a tela mostra ("opt 4.58" em SimuCard) e que /pvbtcurve devolveu;
PVBT(q_opt) vem de metadata.pvbt_at_q_opt (calculado na origem). O que este
modulo faz e so achar a linha de menor PVBT DA GRADE varrida (min/argmin) e
formatar. Sao dois "otimos" distintos e o arquivo os mantem separados:

  - otimo exato:      q_opt / PVBT(q_opt)  (Eq. 33, independe da grade)
  - menor PVBT varrido: depende da grade; se cair na 1a/ultima linha, o otimo
    real esta fora da faixa varrida ("Minimo na borda...").

Curvas EXPERIMENTAIS so entram como pontos (aba propria + marcadores na
figura): sem otimo, sem janela, sem Nota, nada de metadata inferido.
"""

from __future__ import annotations

import io

import xlsxwriter

from app.schemas import LinearExperimentalCurve, LinearExportRequest, LinearModelCurve
from app.services import export_plots as ep
from app.services.export_workbook import (
    RESUMO_IMAGE_TARGET_WIDTH_PX,
    _dedupe_sheet_name,
    _Formats,
    _insert_scaled_image,
    _pick_number_format,
    _sanitize_sheet_name,
    _title_span_cols,
    _write_figure_title,
)

Q_UNIT = "cm³/min"

SIM_HEADER = [
    f"q0 [{Q_UNIT}]", "PVBt", "iv [m/s]", "1/Da", "wv [m/s]", "vbt [cm³]", "tbt [s]", "dv [m/s]", "Nota",
]
NUMERIC_COLS = (0, 7)
EXP_HEADER = ["Curve ID", f"q0 [{Q_UNIT}]", "PVBt"]


def fmt_flow(v: float) -> str:
    """Espelho de fmtBblMin (validityWindow.ts) -- a MESMA regra de casas que
    a tela usa pra escrever q_opt ("4.58"), so pro TEXTO da Nota. As celulas
    numericas guardam o valor em precisao total."""
    if v < 0.1:
        return f"{v:.2g}"
    return f"{v:.2f}" if v < 10 else f"{v:.1f}"


def analyze_linear_curve(curve: LinearModelCurve) -> dict:
    """Otimo exato (metadata) + menor PVBT varrido (grade) de UMA curva."""
    n = len(curve.flowratepoints)
    min_idx, min_v = -1, float("inf")
    for i in range(n):
        v = curve.pvbtpoints[i] if i < len(curve.pvbtpoints) else None
        if v is not None and v > 0 and v < min_v:
            min_v, min_idx = v, i

    meta = curve.metadata or {}
    q_opt = meta.get("q_opt_cm3_min")
    return {
        "min_idx": min_idx,
        "is_border": min_idx in (0, n - 1),
        "min_pvbt": min_v if min_idx >= 0 else None,
        "min_q": curve.flowratepoints[min_idx] if min_idx >= 0 else None,
        "q_opt": q_opt,
        "pvbt_at_q_opt": meta.get("pvbt_at_q_opt") if q_opt is not None else None,
        "window_min": meta.get("validity_min_cm3_min"),
        "window_max": meta.get("validity_max_cm3_min"),
    }


def optimum_marker(info: dict, flowratepoints: list[float]) -> tuple[float, float] | None:
    """Marcador do otimo EXATO (q_opt, PVBT(q_opt)) de metadata; None se nao ha
    q_opt/pvbt_at_q_opt (curva antiga) ou se q_opt cai fora da faixa varrida.
    Espelho de linearOptimumMarker (linearExport.ts) -- travado por
    shared-fixtures/linear_optimum_cases.json."""
    q, y = info["q_opt"], info["pvbt_at_q_opt"]
    if q is None or y is None or not flowratepoints:
        return None
    if q < min(flowratepoints) or q > max(flowratepoints):
        return None
    return (q, y)


def build_note(info: dict, i: int) -> str:
    """Convencao do radial: so a linha de menor PVBT varrido tem Nota; se for
    a 1a/ultima, o otimo real esta fora da faixa varrida."""
    if i != info["min_idx"]:
        return ""
    q_txt = f"; q_opt = {fmt_flow(info['q_opt'])} {Q_UNIT}" if info["q_opt"] is not None else ""
    if info["is_border"]:
        return f"Mínimo na borda da faixa simulada{q_txt}"
    return f"PVBT mínimo desta simulação{q_txt}"


def build_model_rows(curve: LinearModelCurve) -> tuple[list[list], set[int], dict]:
    info = analyze_linear_curve(curve)
    n = len(curve.flowratepoints)

    def at(arr, i):
        return arr[i] if i < len(arr) else None

    rows = []
    for i in range(n):
        rows.append([
            curve.flowratepoints[i],
            at(curve.pvbtpoints, i),
            at(curve.insterticialvelocity, i),
            at(curve.ida, i),
            at(curve.wormholevelocity, i),
            at(curve.volumetobt, i),
            at(curve.timetobt, i),
            at(curve.darcyvelocity, i),
            build_note(info, i),
        ])
    highlight = {info["min_idx"]} if info["min_idx"] >= 0 else set()
    return rows, highlight, info


def build_summary_rows(info: dict) -> list[tuple[str, object]]:
    """Bloco por curva: otimo exato primeiro, menor varrido separado."""
    na = "não disponível"
    exact = info["q_opt"] is not None
    return [
        (f"q_opt [{Q_UNIT}]", info["q_opt"] if exact else na),
        ("PVBT at q_opt", info["pvbt_at_q_opt"] if info["pvbt_at_q_opt"] is not None else na),
        (f"Recommended window min = q_opt/10 [{Q_UNIT}]", info["window_min"] if exact else na),
        (f"Recommended window max = 10·q_opt [{Q_UNIT}]", info["window_max"] if exact else na),
        ("Lowest PVBT in sweep (grid-dependent)", info["min_pvbt"] if info["min_pvbt"] is not None else na),
        (f"Flowrate at lowest swept PVBT [{Q_UNIT}]", info["min_q"] if info["min_q"] is not None else na),
    ]


def _write_model_sheet(wb, fmts: _Formats, name: str, curve: LinearModelCurve):
    rows, highlight, info = build_model_rows(curve)
    summary = build_summary_rows(info)

    ws = wb.add_worksheet(name)
    ws.merge_range(0, 0, 0, 1, "OPTIMUM SUMMARY", fmts.section_header)
    label_w = len("OPTIMUM SUMMARY")
    for r, (label, value) in enumerate(summary, start=1):
        ws.write(r, 0, label, fmts.input_label)
        if isinstance(value, (int, float)):
            ws.write_number(r, 1, value, wb_num_fmt(fmts, "0.0000"))
        else:
            ws.write(r, 1, value, fmts.input_value)
        label_w = max(label_w, len(label))

    header_row = len(summary) + 2
    for c, label in enumerate(SIM_HEADER):
        ws.write(header_row, c, label, fmts.col_header)

    lo, hi = NUMERIC_COLS
    col_formats = [
        _pick_number_format([r[c] for r in rows if isinstance(r[c], (int, float))])
        for c in range(lo, hi + 1)
    ]
    col_widths = [max(len(SIM_HEADER[c]), 8) for c in range(len(SIM_HEADER))]
    col_widths[0] = max(col_widths[0], label_w)
    for r_idx, row in enumerate(rows):
        is_hl = r_idx in highlight
        for c, val in enumerate(row):
            num_fmt = col_formats[c - lo] if lo <= c <= hi and isinstance(val, (int, float)) else None
            fmt = fmts.data(num_fmt, is_hl)
            if val is None:
                ws.write_blank(header_row + 1 + r_idx, c, None, fmt)
            else:
                ws.write(header_row + 1 + r_idx, c, val, fmt)
            col_widths[c] = max(col_widths[c], len(str(val)) if val is not None else 0)
    for c, w in enumerate(col_widths):
        ws.set_column(c, c, min(w + 3, 60))
    ws.set_column(1, 1, max(col_widths[1] + 3, 24))
    ws.freeze_panes(header_row + 1, 0)


def wb_num_fmt(fmts: _Formats, num_format: str):
    """Valor numerico do bloco-resumo: mesmo visual de input_value + formato."""
    key = ("summary", num_format)
    if key not in fmts._cache:
        fmts._cache[key] = fmts.wb.add_format({
            "bg_color": "#D9E1F2", "font_color": "#0F172A", "border": 1,
            "border_color": "#B0C4DE", "align": "center", "valign": "vcenter",
            "num_format": num_format,
        })
    return fmts._cache[key]


def _build_inputs_rows(curves: list[LinearModelCurve]) -> list[tuple[str, list]]:
    def col(fn):
        return [fn(c) for c in curves]

    def blank_if_none(v):
        return "" if v is None else v

    rows: list[tuple[str, list]] = [
        ("Simulation ID", col(lambda c: c.id or "—")),
        ("Flow Regime", col(lambda c: "linear")),
        ("Rock Type", col(lambda c: c.rock_type)),
        ("Acid Type", col(lambda c: c.acid_type)),
        ("Acid Concentration (w/w)", col(lambda c: blank_if_none(c.acid_concentration))),
        ("Porosity", col(lambda c: blank_if_none(c.porosity))),
        ("Temperature (°C)", col(lambda c: blank_if_none(c.temperature_c))),
        ("Temperature (K)", col(lambda c: "" if c.temperature_c is None else round(c.temperature_c + 273.15, 2))),
        ("Core Length (in)", col(lambda c: blank_if_none(c.core_length_in))),
        ("Core Diameter (in)", col(lambda c: blank_if_none(c.core_diameter_in))),
        (f"Flowrate Sweep Min ({Q_UNIT})", col(lambda c: min(c.flowratepoints) if c.flowratepoints else "")),
        (f"Flowrate Sweep Max ({Q_UNIT})", col(lambda c: max(c.flowratepoints) if c.flowratepoints else "")),
        ("Number of steps", col(lambda c: len(c.flowratepoints))),
    ]
    return rows


def _write_inputs_sheet(wb, fmts: _Formats, curves: list[LinearModelCurve]):
    ws = wb.add_worksheet("Inputs")
    ncols = 1 + max(len(curves), 1)
    ws.merge_range(0, 0, 0, ncols - 1, "INPUT PARAMETERS", fmts.section_header)
    if not curves:
        ws.write(1, 0, "Model curves", fmts.input_label)
        ws.write(1, 1, "none (experimental points only)", fmts.input_value)
        ws.set_column(0, 0, 24)
        ws.set_column(1, 1, 36)
        ws.freeze_panes(1, 0)
        return
    widths = [len("INPUT PARAMETERS")] + [8] * len(curves)
    for r, (label, values) in enumerate(_build_inputs_rows(curves), start=1):
        ws.write(r, 0, label, fmts.input_label)
        widths[0] = max(widths[0], len(label))
        for j, v in enumerate(values, start=1):
            ws.write(r, j, v, fmts.input_value)
            widths[j] = max(widths[j], len(str(v)))
    ws.set_column(0, 0, min(widths[0] + 3, 60))
    for j in range(1, ncols):
        ws.set_column(j, j, max(24, min(widths[j] + 3, 60)))
    ws.freeze_panes(1, 0)


def _write_experimental_sheet(wb, fmts: _Formats, exp: list[LinearExperimentalCurve]):
    ws = wb.add_worksheet("Experimental")
    for c, label in enumerate(EXP_HEADER):
        ws.write(0, c, label, fmts.col_header)
    ws.write(0, 4, "Experimental points only — no optimum, validity window or model metadata.",
             fmts.input_label)
    r = 1
    width_id = len(EXP_HEADER[0])
    for curve in exp:
        for i, q in enumerate(curve.flowratepoints):
            y = curve.pvbtpoints[i] if i < len(curve.pvbtpoints) else None
            ws.write(r, 0, curve.id, fmts.data(None, False))
            ws.write(r, 1, q, fmts.data("0.0000", False))
            if y is None:
                ws.write_blank(r, 2, None, fmts.data(None, False))
            else:
                ws.write(r, 2, y, fmts.data("0.0000", False))
            width_id = max(width_id, len(curve.id))
            r += 1
    ws.set_column(0, 0, min(width_id + 3, 60))
    ws.set_column(1, 2, 16)
    ws.set_column(4, 4, 70)
    ws.freeze_panes(1, 0)


def _plot_data(req: LinearExportRequest):
    curves = []
    for idx, c in enumerate(req.curves):
        meta = c.metadata or {}
        marker = optimum_marker(analyze_linear_curve(c), c.flowratepoints)
        curves.append(ep.SimCurveData(
            label=c.id,
            color=ep.color_for_index(idx),
            flowratepoints=c.flowratepoints,
            acidvolumepoints=c.pvbtpoints,
            q_opt=marker[0] if marker else None,
            validity_min=meta.get("validity_min_cm3_min"),
            validity_max=meta.get("validity_max_cm3_min"),
            y_opt=marker[1] if marker else None,
            join_at_boundary=True,
        ))
    exps = [
        ep.ExpPointsData(label=e.id, color=ep.color_for_index(len(req.curves) + j),
                         x=e.flowratepoints, y=e.pvbtpoints)
        for j, e in enumerate(req.experimental_curves)
    ]
    return curves, exps


def build_linear_figure(req: LinearExportRequest, size: str = "single"):
    """UMA figura: todas as curvas de modelo (linhas, otimo exato marcado,
    banda cinza fora da janela) + experimentais (so marcadores). log-log."""
    curves, exps = _plot_data(req)
    return ep.build_simulation_figure(
        curves, size=size, show_validity_band=req.options.show_validity_band,
        x_label=f"Flowrate, {Q_UNIT}", y_label="PVBt", x_log=True,
        exp_points=exps, optimum_legend_label="q_opt (exact, Eq. 33)",
    )


def generate_linear_figure(req: LinearExportRequest, size: str = "single") -> bytes:
    return ep._savefig_png(build_linear_figure(req, size))


def _write_figures_sheet(wb, fmts: _Formats, req: LinearExportRequest):
    ws = wb.add_worksheet("Figures")
    png = generate_linear_figure(req, size="single")
    span_cols = _title_span_cols(RESUMO_IMAGE_TARGET_WIDTH_PX)
    _write_figure_title(ws, fmts, 0, 0, span_cols, "PVBt Chart")
    _insert_scaled_image(ws, png, row=1, col=0, target_width_px=RESUMO_IMAGE_TARGET_WIDTH_PX)


def build_linear_workbook(req: LinearExportRequest, include_images: bool = True) -> bytes:
    """include_images=False: mesma estrutura sem a aba Figures."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fmts = _Formats(wb)

    _write_inputs_sheet(wb, fmts, req.curves)
    if include_images and (req.curves or req.experimental_curves):
        _write_figures_sheet(wb, fmts, req)

    used = {"Inputs", "Figures", "Experimental"}
    for c in req.curves:
        name = _dedupe_sheet_name(_sanitize_sheet_name(f"Sim {c.id}"), used)
        _write_model_sheet(wb, fmts, name, c)

    if req.experimental_curves:
        _write_experimental_sheet(wb, fmts, req.experimental_curves)

    wb.close()
    return buf.getvalue()
