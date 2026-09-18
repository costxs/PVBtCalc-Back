"""
export_workbook.py
------------------------------------------------------------------
Monta o .xlsx do export radial (XlsxWriter) com as MESMAS abas/ordem/
destaques/notas/formatos que o front ja produzia client-side (src/tools/
export.tsx) -- porta fiel pra Python, so mudando a biblioteca (aqui
XlsxWriter tem freeze_panes nativo, sem precisar do pos-processamento de
zip que o front fazia com fflate). Nenhum calculo novo: todo valor vem
pronto do payload (RadialExportRequest) ou e so reformatacao/agrupamento
(min/max, mais proximo de um alvo, etc.) -- a mesma classe de operacao que
export.tsx ja fazia.
"""

from __future__ import annotations

import io
import math
from typing import Optional

import xlsxwriter

from app.schemas import DesignPlotSeries, RadialCurveResult, RadialExportRequest
from app.services import export_plots as ep

SECTION_HEADER_BG = "#1F4E78"
COL_HEADER_BG = "#2F75B5"
INPUT_VALUE_BG = "#D9E1F2"
HIGHLIGHT_BG = "#FFF2CC"
BORDER_COLOR = "#B0C4DE"

IMAGE_TARGET_WIDTH_PX = 480
RESUMO_IMAGE_TARGET_WIDTH_PX = IMAGE_TARGET_WIDTH_PX
# Excel usa 96 dpi como referencia pra "escala 1.0" -- os PNGs do figure
# pack saem a 300 dpi (dpi=300 no export_plots.py), entao a largura exibida
# por padrao (x_scale=1.0) ja e menor que a largura em pixels do arquivo.
DEFAULT_DPI = 96.0
# Coluna J (0-indexed 9) -- pedido explicito, fixo em toda aba de dados
# (Sim/Design/Skin) independente do numero de colunas da tabela, pra a
# imagem ficar alinhada ao rolar entre abas. Titulo ocupa a linha 2
# (0-indexed 1); imagem vai uma linha abaixo dele (0-indexed 2).
IMAGE_ANCHOR_COL = 9
IMAGE_TITLE_ROW = 1
IMAGE_ANCHOR_ROW = IMAGE_TITLE_ROW + 1
# Altura de linha padrao do Excel (~15pt) em pixels, usada so pra estimar
# quantas linhas pular entre figuras na aba "Resumo graficos".
DEFAULT_ROW_HEIGHT_PX = 20
# Altura (em pontos) da linha do titulo da figura -- pedido explicito.
IMAGE_TITLE_ROW_HEIGHT = 24
# Largura de coluna (unidade Excel) fixada nas colunas que o titulo mescla,
# pra o calculo de quantas colunas cobrir ~N px ser previsivel: nessa
# largura, 1 coluna ~= 69 px (Calibri 11, largura padrao do Excel).
TITLE_COLUMN_WIDTH_UNITS = 9.14
TITLE_COLUMN_WIDTH_PX = 69


def _sanitize_sheet_name(name: str) -> str:
    for ch in ':\\/?*[]':
        name = name.replace(ch, '')
    return name[:31]


def _dedupe_sheet_name(name: str, used: set) -> str:
    candidate = name
    n = 2
    while candidate in used:
        suffix = f" {n}"
        candidate = name[: 31 - len(suffix)] + suffix
        n += 1
    used.add(candidate)
    return candidate


def _pick_number_format(values: list) -> str:
    nonzero = [v for v in values if isinstance(v, (int, float)) and v != 0]
    if not nonzero:
        return "0.0000"
    needs_sci = any(abs(v) < 0.001 or abs(v) >= 1e5 for v in nonzero)
    return "0.000E+00" if needs_sci else "0.0000"


def _fmt_target(t: float) -> str:
    if float(t).is_integer():
        return str(int(t))
    s = f"{t:.2f}".rstrip('0').rstrip('.')
    return s


def _join_pt(items: list[str]) -> str:
    if not items:
        return ''
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} e {items[1]}"
    return f"{', '.join(items[:-1])} e {items[-1]}"


class _Formats:
    """Cache de formatos XlsxWriter -- criar um objeto por combinacao usada
    em vez de um por celula (limite pratico de formatos do Excel)."""

    def __init__(self, wb: xlsxwriter.Workbook):
        self.wb = wb
        self._cache: dict[tuple, object] = {}
        self.section_header = wb.add_format({
            "bg_color": SECTION_HEADER_BG, "font_color": "white", "bold": True,
            "align": "center", "valign": "vcenter", "font_size": 12,
        })
        self.col_header = wb.add_format({
            "bg_color": COL_HEADER_BG, "font_color": "white", "bold": True,
            "align": "center", "valign": "vcenter", "font_size": 11,
            "text_wrap": True, "border": 1, "border_color": BORDER_COLOR,
        })
        self.input_label = wb.add_format({
            "bold": True, "font_color": "#1F2937", "border": 1,
            "border_color": BORDER_COLOR, "align": "left", "valign": "vcenter",
        })
        self.input_value = wb.add_format({
            "bg_color": INPUT_VALUE_BG, "font_color": "#0F172A", "border": 1,
            "border_color": BORDER_COLOR, "align": "center", "valign": "vcenter",
        })

    def data(self, num_format: Optional[str], highlighted: bool):
        key = (num_format, highlighted)
        if key not in self._cache:
            spec = {
                "border": 1, "border_color": BORDER_COLOR,
                "align": "right", "valign": "vcenter", "font_size": 10.5,
            }
            if highlighted:
                spec["bg_color"] = HIGHLIGHT_BG
                spec["bold"] = True
            if num_format:
                spec["num_format"] = num_format
            self._cache[key] = self.wb.add_format(spec)
        return self._cache[key]


def _write_simple_sheet(
    wb: xlsxwriter.Workbook,
    fmts: _Formats,
    name: str,
    header: list[str],
    rows: list[list],
    highlighted_rows: set[int],
    numeric_col_range: tuple[int, int],
    image_png: Optional[bytes] = None,
    image_title: Optional[str] = None,
):
    ws = wb.add_worksheet(name)
    for c, label in enumerate(header):
        ws.write(0, c, label, fmts.col_header)

    lo, hi = numeric_col_range
    col_formats = []
    for c in range(lo, hi + 1):
        col_vals = [r[c] for r in rows if isinstance(r[c], (int, float))]
        col_formats.append(_pick_number_format(col_vals))

    col_widths = [max(len(str(header[c])), 8) for c in range(len(header))]
    for r_idx, row in enumerate(rows):
        is_hl = r_idx in highlighted_rows
        for c, val in enumerate(row):
            num_fmt = col_formats[c - lo] if lo <= c <= hi and isinstance(val, (int, float)) else None
            fmt = fmts.data(num_fmt, is_hl)
            if val is None:
                ws.write_blank(r_idx + 1, c, None, fmt)
            else:
                ws.write(r_idx + 1, c, val, fmt)
            col_widths[c] = max(col_widths[c], len(str(val)) if val is not None else 0)

    for c, w in enumerate(col_widths):
        ws.set_column(c, c, min(w + 3, 60))

    ws.freeze_panes(1, 0)

    if image_png is not None:
        span_cols = _title_span_cols(IMAGE_TARGET_WIDTH_PX)
        _write_figure_title(ws, fmts, IMAGE_TITLE_ROW, IMAGE_ANCHOR_COL, span_cols, image_title or "")
        _insert_scaled_image(ws, image_png, row=IMAGE_ANCHOR_ROW, col=IMAGE_ANCHOR_COL)

    return ws


def _insert_scaled_image(ws, png_bytes: bytes, row: int, col: int,
                          target_width_px: int = IMAGE_TARGET_WIDTH_PX) -> float:
    """Insere a imagem escalada pra `target_width_px` de largura EXIBIDA no
    Excel e devolve a altura exibida resultante (px).

    XlsxWriter posiciona a imagem na sua resolucao nativa em pixels assumindo
    96 dpi pra x_scale/y_scale = 1.0. Os PNGs do figure pack saem a 300 dpi
    (mais nitidos, menores em "pixels exibidos" do que em pixels de arquivo),
    entao a largura base exibida a escala 1.0 e width_px * 96/dpi_png, NAO
    width_px -- calcular o scale direto sobre width_px reduz a imagem por um
    fator extra de 96/dpi_png.
    """
    from PIL import Image
    im = Image.open(io.BytesIO(png_bytes))
    width_px, height_px = im.size
    dpi_png = im.info.get("dpi", (DEFAULT_DPI, DEFAULT_DPI))[0] or DEFAULT_DPI
    base_width_px = width_px * DEFAULT_DPI / dpi_png
    scale = target_width_px / base_width_px if base_width_px else 1.0
    ws.insert_image(row, col, "figure.png", {
        "image_data": io.BytesIO(png_bytes),
        "x_scale": scale, "y_scale": scale,
    })
    return height_px * DEFAULT_DPI / dpi_png * scale


def _title_span_cols(target_width_px: float) -> int:
    """Quantas colunas (a TITLE_COLUMN_WIDTH_UNITS cada) somam >= target_width_px."""
    return max(1, math.ceil(target_width_px / TITLE_COLUMN_WIDTH_PX))


def _write_figure_title(ws, fmts: "_Formats", row: int, col: int, span_cols: int, text: str):
    """Barra de titulo da figura -- MESMO estilo do cabecalho 'INPUT
    PARAMETERS' da aba Inputs (fmts.section_header: fundo #1F4E78, fonte
    branca em negrito 12pt, centralizado). Fixa a largura das colunas
    mescladas (TITLE_COLUMN_WIDTH_UNITS ~= TITLE_COLUMN_WIDTH_PX px cada)
    pra a celula mesclada cobrir de forma previsivel a largura exibida da
    imagem, que fica ancorada na linha seguinte."""
    ws.set_column(col, col + span_cols - 1, TITLE_COLUMN_WIDTH_UNITS)
    ws.set_row(row, IMAGE_TITLE_ROW_HEIGHT)
    if span_cols > 1:
        ws.merge_range(row, col, row, col + span_cols - 1, text, fmts.section_header)
    else:
        ws.write(row, col, text, fmts.section_header)


# --- Simulation --------------------------------------------------------

SIM_HEADER = ["q0 [gal/(ft.min)]", "V_A [gal/ft]", "iv [m/s]", "wv [m/s]", "dv [m/s]", "1/Da", "tbt [s]", "Nota"]


def _build_simulation_rows(curve: RadialCurveResult) -> tuple[list[list], set[int]]:
    n = len(curve.flowratepoints)
    min_idx, min_v = -1, float("inf")
    for i in range(n):
        v = curve.acidvolumepoints[i] if i < len(curve.acidvolumepoints) else None
        if v is not None and v > 0 and v < min_v:
            min_v, min_idx = v, i

    is_border = min_idx in (0, n - 1)
    q_opt = curve.metadata.q_opt_gal_ft_min if curve.metadata else None
    q_opt_str = f"{q_opt:.4f}" if q_opt is not None else None

    rows = []
    for i in range(n):
        note = ""
        if i == min_idx:
            if is_border:
                note = (f"Mínimo na borda da faixa simulada; q_opt = {q_opt_str} gal/(ft·min)"
                        if q_opt_str else "Mínimo na borda da faixa simulada")
            else:
                note = (f"V_A mínimo desta simulação; q_opt = {q_opt_str} gal/(ft·min)"
                        if q_opt_str else "V_A mínimo desta simulação")
        rows.append([
            curve.flowratepoints[i],
            curve.acidvolumepoints[i] if i < len(curve.acidvolumepoints) else None,
            curve.insterticialvelocity[i] if i < len(curve.insterticialvelocity) else None,
            curve.wormholevelocity[i] if i < len(curve.wormholevelocity) else None,
            curve.darcyvelocity[i] if i < len(curve.darcyvelocity) else None,
            curve.ida[i] if i < len(curve.ida) else None,
            curve.timetobt[i] if i < len(curve.timetobt) else None,
            note,
        ])
    highlight = {min_idx} if min_idx >= 0 else set()
    return rows, highlight


def _simulation_sheet_name(curve: RadialCurveResult) -> str:
    return _sanitize_sheet_name(f"Sim {curve.target_label}")


def _sim_curve_to_plot_data(curve: RadialCurveResult, color: str) -> ep.SimCurveData:
    meta = curve.metadata
    return ep.SimCurveData(
        label=curve.target_label,
        color=color,
        flowratepoints=curve.flowratepoints,
        acidvolumepoints=curve.acidvolumepoints,
        q_opt=meta.q_opt_gal_ft_min if meta else None,
        validity_min=meta.validity_min_gal_ft_min if meta else None,
        validity_max=meta.validity_max_gal_ft_min if meta else None,
    )


def _append_simulation_sheets(wb, fmts, curves: list[RadialCurveResult], show_validity_band: bool,
                               include_images: bool = True):
    used = set()
    for idx, c in enumerate(curves):
        rows, highlight = _build_simulation_rows(c)
        plot = ep.render_simulation_figure(
            [_sim_curve_to_plot_data(c, ep.color_for_index(idx))],
            size="single", show_validity_band=show_validity_band,
        ) if include_images else None
        name = _dedupe_sheet_name(_simulation_sheet_name(c), used)
        _write_simple_sheet(wb, fmts, name, SIM_HEADER, rows, highlight, (0, 6), image_png=plot,
                             image_title="Simulation Chart")


# --- Design Plot ---------------------------------------------------------

DESIGN_HEADER = ["L [ft]", "q_opt [gal/(ft.min)]", "V_opt [gal/ft]", "tbt [min]", "Temperatura [K]", "Nota"]


def _design_rows_for_temp(series: DesignPlotSeries, payzone_thickness_ft: Optional[float]) -> list[dict]:
    rate = series.optimum_rate_series
    vol = series.optimum_volume_series
    n = min(len(rate), len(vol))
    rows = []
    for i in range(n):
        q_opt = rate[i][0]
        v_opt = vol[i][0]
        rows.append({
            "comprimento": rate[i][1],
            "q_opt": q_opt,
            "v_opt": v_opt,
            "tbt_min": (v_opt / q_opt) if q_opt else None,
            "temperatura": series.temperature_k,
        })
    rows.sort(key=lambda r: r["comprimento"])
    return rows


def _append_design_sheets(wb, fmts, design_series: list[DesignPlotSeries], payzone_thickness_ft,
                           targets: Optional[list[float]], include_images: bool = True):
    used = set()
    clean_targets = [t for t in (targets or []) if t is not None]
    sorted_series = sorted(design_series, key=lambda s: s.temperature_k)

    for idx, series in enumerate(sorted_series):
        rows = _design_rows_for_temp(series, payzone_thickness_ft)
        if not rows:
            continue
        last_l = rows[-1]["comprimento"]
        half_step = (last_l - rows[0]["comprimento"]) / (len(rows) - 1) / 2 if len(rows) > 1 else float("inf")

        notes_by_row: dict[int, list[str]] = {}
        highlight: set[int] = set()
        missed: list[float] = []

        for t in clean_targets:
            best_idx, best_diff = -1, float("inf")
            for i, r in enumerate(rows):
                diff = abs(r["comprimento"] - t)
                if diff < best_diff:
                    best_diff, best_idx = diff, i
            if best_idx >= 0 and best_diff <= half_step:
                highlight.add(best_idx)
                notes_by_row.setdefault(best_idx, []).append(
                    f"Alvo {_fmt_target(t)} ft (L = {rows[best_idx]['comprimento']:.2f} ft)"
                )
            elif t > last_l:
                missed.append(t)

        if missed:
            last_idx = len(rows) - 1
            highlight.add(last_idx)
            label = "Alvo" if len(missed) == 1 else "Alvos"
            verb = "não atingido" if len(missed) == 1 else "não atingidos"
            notes_by_row.setdefault(last_idx, []).append(
                f"{label} {_join_pt([_fmt_target(t) for t in missed])} ft {verb} — "
                f"tabela termina em {last_l:.2f} ft (limite 1000 gal/ft)"
            )

        sheet_rows = [
            [r["comprimento"], r["q_opt"], r["v_opt"], r["tbt_min"], r["temperatura"],
             "; ".join(notes_by_row.get(i, []))]
            for i, r in enumerate(rows)
        ]

        plot = ep.render_design_figure(
            [ep.DesignSeriesData(
                label=f"{series.temperature_k} K", color=ep.color_for_index(idx),
                optimum_rate_series=series.optimum_rate_series,
                optimum_volume_series=series.optimum_volume_series,
            )],
            size="single",
        ) if include_images else None
        name = _dedupe_sheet_name(_sanitize_sheet_name(f"Design {round(series.temperature_k)} K"), used)
        _write_simple_sheet(wb, fmts, name, DESIGN_HEADER, sheet_rows, highlight, (0, 4), image_png=plot,
                             image_title="Design Plot")


# --- Skin ------------------------------------------------------------------

SKIN_HEADER = ["V_A [gal/ft]", "skin", "comprimento [ft]", "Nota"]


def _append_skin_sheets(wb, fmts, skin_series: dict, target_skin: Optional[float], include_images: bool = True):
    used = set()
    keys = sorted(skin_series.keys(), key=lambda k: float(k))
    for idx, key in enumerate(keys):
        points = skin_series[key]
        if not points:
            continue
        target_idx = len(points) - 1
        if target_skin is not None:
            best_diff = float("inf")
            for i, p in enumerate(points):
                diff = abs(p.y - target_skin)
                if diff < best_diff:
                    best_diff, target_idx = diff, i

        rows = []
        for i, p in enumerate(points):
            note = ""
            if i == target_idx:
                note = f"Skin alvo (mais próximo de {target_skin})" if target_skin is not None else "Skin final"
            rows.append([p.x, p.y, p.l_ft, note])

        plot = ep.render_skin_figure(
            [ep.SkinSeriesData(
                label=f"{key} bbl/min", color=ep.color_for_index(idx),
                points=[(p.x, p.y) for p in points],
            )],
            size="single",
        ) if include_images else None
        name = _dedupe_sheet_name(_sanitize_sheet_name(f"Skin {key} bbl-min"), used)
        _write_simple_sheet(wb, fmts, name, SKIN_HEADER, rows, {target_idx}, (0, 2), image_png=plot,
                             image_title="Skin Evolution")


# --- Inputs ------------------------------------------------------------------

def _build_inputs_rows(req: RadialExportRequest) -> list[list]:
    inp = req.inputs
    rows: list[list] = [
        ["Simulation ID", inp.simulation_id or "—"],
        ["Flow Regime", "radial"],
        ["Rock Type", inp.rock_type or ""],
        ["Acid Type", inp.acid_type or ""],
    ]
    if inp.acid_concentration is not None:
        rows.append(["Acid Concentration (w/w)", inp.acid_concentration])
    if inp.porosity is not None:
        rows.append(["Porosity", inp.porosity])
    if inp.temperature_k is not None:
        rows.append(["Temperature (K)", inp.temperature_k])
        rows.append(["Temperature (°C)", round(inp.temperature_k - 273.15, 2)])
    if inp.wellbore_size_in is not None:
        rows.append([f"Wellbore Size (in) [{inp.wellbore_mode}]", inp.wellbore_size_in])
    if inp.wellbore_radius_in is not None:
        rows.append(["Wellbore Radius (in)", inp.wellbore_radius_in])
    if inp.payzone_thickness_ft is not None:
        rows.append(["Payzone Thickness (ft)", inp.payzone_thickness_ft])
    if inp.flowrate_min_bbl_min is not None:
        rows.append(["Flowrate Sweep Min (bbl/min)", inp.flowrate_min_bbl_min])
    if inp.flowrate_max_bbl_min is not None:
        rows.append(["Flowrate Sweep Max (bbl/min)", inp.flowrate_max_bbl_min])

    all_q = [q for c in req.curves for q in c.flowratepoints]
    if all_q:
        rows.append(["Flowrate Sweep Min (gal/(ft.min))", min(all_q)])
        rows.append(["Flowrate Sweep Max (gal/(ft.min))", max(all_q)])

    if inp.number_of_steps is not None:
        rows.append(["Number of steps", inp.number_of_steps])

    rows.append(["Targets", inp.targets_label or "—"])
    rows.append(["Flowing Fraction (f)", inp.flowing_fraction if inp.flowing_fraction is not None else "não disponível"])
    return rows


def _write_inputs_sheet(wb, fmts, req: RadialExportRequest):
    ws = wb.add_worksheet("Inputs")
    rows = _build_inputs_rows(req)
    ws.merge_range(0, 0, 0, 1, "INPUT PARAMETERS", fmts.section_header)
    max_len = len("INPUT PARAMETERS")
    for r, (label, value) in enumerate(rows, start=1):
        ws.write(r, 0, label, fmts.input_label)
        ws.write(r, 1, value, fmts.input_value)
        max_len = max(max_len, len(str(label)), len(str(value)))
    ws.set_column(0, 0, min(max_len + 3, 60))
    ws.set_column(1, 1, 24)
    ws.freeze_panes(1, 0)


# --- Figuras combinadas (respeitam chips ativos / limites, se enviados) ----

def generate_all_figures(req: RadialExportRequest, size: str = "single") -> dict[str, bytes]:
    """Devolve {nome_estavel: png_bytes} -- individuais (todas as curvas,
    sem filtro de chip) + combinadas (respeitam chips/limites ativos)."""
    out: dict[str, bytes] = {}
    opt = req.options

    for idx, c in enumerate(req.curves):
        stem = f"simulation_{c.target_label}".replace(' ', '')
        out[stem] = ep.render_simulation_figure(
            [_sim_curve_to_plot_data(c, ep.color_for_index(idx))],
            size=size, show_validity_band=opt.show_validity_band,
        )

    active_targets = set(opt.active_targets) if opt.active_targets is not None else None
    sim_plot_data = [
        _sim_curve_to_plot_data(c, ep.color_for_index(idx))
        for idx, c in enumerate(req.curves)
        if active_targets is None or c.target_label in active_targets
    ]
    if sim_plot_data:
        out["simulation_all"] = ep.render_simulation_figure(
            sim_plot_data, size=size, show_validity_band=opt.show_validity_band,
            show_optimum_path=opt.show_optimum_path,
            x_limits=opt.sim_x_limits.dict() if opt.sim_x_limits else None,
            y_limits=opt.sim_y_limits.dict() if opt.sim_y_limits else None,
        )

    sorted_series = sorted(req.design_series, key=lambda s: s.temperature_k)
    for idx, s in enumerate(sorted_series):
        stem = f"design_{s.temperature_k}K".replace(' ', '')
        out[stem] = ep.render_design_figure(
            [ep.DesignSeriesData(label=f"{s.temperature_k} K", color=ep.color_for_index(idx),
                                  optimum_rate_series=s.optimum_rate_series,
                                  optimum_volume_series=s.optimum_volume_series)],
            size=size,
        )

    active_temps = set(opt.active_temperatures) if opt.active_temperatures is not None else None
    design_plot_data = [
        ep.DesignSeriesData(label=f"{s.temperature_k} K", color=ep.color_for_index(idx),
                             optimum_rate_series=s.optimum_rate_series,
                             optimum_volume_series=s.optimum_volume_series)
        for idx, s in enumerate(sorted_series)
        if active_temps is None or s.temperature_k in active_temps
    ]
    if design_plot_data:
        out["design_all"] = ep.render_design_figure(
            design_plot_data, size=size,
            x_limits=opt.design_x_limits.dict() if opt.design_x_limits else None,
            y_limits=opt.design_y_limits.dict() if opt.design_y_limits else None,
        )

    skin_keys = sorted(req.skin_series.keys(), key=lambda k: float(k))
    for idx, key in enumerate(skin_keys):
        points = req.skin_series[key]
        stem = f"skin_{key}bblmin".replace(' ', '')
        out[stem] = ep.render_skin_figure(
            [ep.SkinSeriesData(label=f"{key} bbl/min", color=ep.color_for_index(idx),
                                points=[(p.x, p.y) for p in points])],
            size=size,
        )

    active_flows = set(opt.active_flowrates) if opt.active_flowrates is not None else None
    skin_plot_data = [
        ep.SkinSeriesData(label=f"{key} bbl/min", color=ep.color_for_index(idx),
                           points=[(p.x, p.y) for p in req.skin_series[key]])
        for idx, key in enumerate(skin_keys)
        if active_flows is None or key in active_flows
    ]
    if skin_plot_data:
        out["skin_all"] = ep.render_skin_figure(
            skin_plot_data, size=size,
            x_limits=opt.skin_x_limits.dict() if opt.skin_x_limits else None,
            y_limits=opt.skin_y_limits.dict() if opt.skin_y_limits else None,
        )

    return out


RESUMO_FIGURE_TITLES = {
    "simulation_all": "Simulation Chart",
    "design_all": "Design Plot",
    "skin_all": "Skin Evolution",
}


def _write_combined_figures_sheet(wb, fmts: _Formats, req: RadialExportRequest):
    ws = wb.add_worksheet("Resumo gráficos")
    figures = generate_all_figures(req, size="single")
    span_cols = _title_span_cols(RESUMO_IMAGE_TARGET_WIDTH_PX)
    row = 1
    for key in ("simulation_all", "design_all", "skin_all"):
        png = figures.get(key)
        if png is None:
            continue
        _write_figure_title(ws, fmts, row - 1, 0, span_cols, RESUMO_FIGURE_TITLES[key])
        displayed_height_px = _insert_scaled_image(
            ws, png, row=row, col=0, target_width_px=RESUMO_IMAGE_TARGET_WIDTH_PX,
        )
        # linhas ocupadas pela altura exibida + 3 linhas de folga antes da
        # proxima figura (titulo incluso), pra nao sobrepor.
        rows_needed = math.ceil(displayed_height_px / DEFAULT_ROW_HEIGHT_PX) + 3
        row += rows_needed


# --- entry point -------------------------------------------------------

def build_workbook(req: RadialExportRequest, include_images: bool = True) -> bytes:
    """include_images=False monta a variante "somente tabelas": sem a aba
    Resumo gráficos (que e so figuras) e sem imagem embutida em nenhuma aba
    de dados -- mesmas abas/formatacao/notas/destaques, arquivo mais leve."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fmts = _Formats(wb)

    _write_inputs_sheet(wb, fmts, req)
    if include_images:
        _write_combined_figures_sheet(wb, fmts, req)

    if req.design_series:
        _append_design_sheets(wb, fmts, req.design_series, req.inputs.payzone_thickness_ft,
                               req.options.target_lengths, include_images=include_images)

    _append_simulation_sheets(wb, fmts, req.curves, req.options.show_validity_band,
                               include_images=include_images)

    if req.skin_series:
        _append_skin_sheets(wb, fmts, req.skin_series, req.options.target_skin, include_images=include_images)

    wb.close()
    return buf.getvalue()
