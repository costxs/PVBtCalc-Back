"""
export_plots.py
------------------------------------------------------------------
Figuras de qualidade de publicacao (matplotlib, PNG 300 dpi) para o export
radial. REGRA DE OURO: este modulo NUNCA importa PVBTradialFunc nem recalcula
nada -- toda funcao aqui recebe os pontos JA CALCULADOS (o mesmo payload que
o front ja exibe) e so decide como desenhar. Interpolacao geometrica (achar
onde uma curva passa num X dado, ou balancear decadas entre dois eixos
espelhados) NAO e fisica -- e so posicionamento de marcador/eixo, a mesma
classe de calculo que Chart.tsx (frontend) ja faz em JS para o grafico
interativo; aqui e so a versao Python para o PNG.

Convencoes fixas (pedido explicito):
- Fonte Arial/Helvetica se disponivel no host, senao DejaVu Sans (sempre
  embutida no matplotlib) -- nunca falha por fonte ausente.
- Tamanhos por coluna de revista (Elsevier/JPSE): "single" 90x70mm,
  "double" 190x120mm.
- Rotulos em ingles, ponto decimal (mesma convencao do app e do artigo).
- Paleta Okabe-Ito (acessivel a daltonismo), cor estavel POR VALOR (mesmo
  alvo/temperatura/vazao) em todas as figuras -- indexada pela posicao do
  valor numa lista ORDENADA, nao pela ordem de chegada no payload.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Sequence

import numpy as np

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import LogLocator, NullFormatter

MM_PER_INCH = 25.4
DPI = 300

FigureSize = Literal["single", "double"]

FIGSIZE_MM: dict[str, tuple[float, float]] = {
    "single": (90.0, 70.0),
    "double": (190.0, 120.0),
}

_PREFERRED_FONTS = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]


def _pick_font() -> str:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _PREFERRED_FONTS:
        if name in available:
            return name
    return "DejaVu Sans"


FONT_FAMILY = _pick_font()

RC_PARAMS = {
    "font.family": FONT_FAMILY,
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7,
    "lines.linewidth": 1.2,
    "axes.linewidth": 0.8,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.top": True,
    "ytick.right": True,
    "xtick.minor.visible": True,
    "ytick.minor.visible": True,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.35,
    "axes.grid": False,
    "savefig.dpi": DPI,
    "figure.dpi": 100,
    "svg.fonttype": "none",
}

# Okabe & Ito (2008) -- paleta qualitativa acessivel a daltonismo, ordem
# fixa. Cor de uma serie = PALETTE[indice_do_valor_numa_lista_ordenada %
# len(PALETTE)] -- nunca a ordem de chegada no payload, pra "5.00 ft" ter
# sempre a mesma cor em toda figura onde aparecer.
PALETTE = [
    "#0072B2",  # blue
    "#E69F00",  # orange
    "#009E73",  # green
    "#D55E00",  # vermillion
    "#CC79A7",  # pink
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
    "#000000",  # black
]

OUT_OF_WINDOW_GRAY = "#616161"
OUT_OF_WINDOW_BAND_ALPHA = 0.08
OPTIMUM_PATH_COLOR = "#4A90E2"


def color_for_index(idx: int) -> str:
    return PALETTE[idx % len(PALETTE)]


def _figsize_inches(size: FigureSize) -> tuple[float, float]:
    w_mm, h_mm = FIGSIZE_MM.get(size, FIGSIZE_MM["single"])
    return (w_mm / MM_PER_INCH, h_mm / MM_PER_INCH)


def _new_figure(size: FigureSize) -> tuple[Figure, FigureCanvasAgg]:
    fig = Figure(figsize=_figsize_inches(size))
    canvas = FigureCanvasAgg(fig)
    return fig, canvas


def _savefig_png(fig: Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=DPI,
        bbox_inches="tight",
        pad_inches=0.02,
        facecolor="white",
    )
    return buf.getvalue()


def _decade_round(vmin: float, vmax: float) -> tuple[float, float]:
    """Arredonda [vmin,vmax] pra decadas inteiras (10**floor, 10**ceil).
    Puramente geometrico (mesmo que Chart.tsx faz em JS) -- nao e fisica."""
    if not (np.isfinite(vmin) and np.isfinite(vmax)) or vmin <= 0 or vmax <= 0:
        return (vmin, vmax)
    lo = 10 ** np.floor(np.log10(vmin))
    hi = 10 ** np.ceil(np.log10(vmax))
    return (float(lo), float(hi))


def _interp_log_y(x0: float, y0: float, x1: float, y1: float, xq: float) -> Optional[float]:
    """Interpola Y (espaco LOG) entre dois pontos conhecidos da curva JA
    CALCULADA, no X pedido -- geometria de desenho (achar onde marcar q_opt
    em cima da linha existente), nao um novo calculo fisico. None se o
    segmento for degenerado ou os Y nao forem positivos (teria log invalido).
    """
    if x1 == x0 or y0 is None or y1 is None or y0 <= 0 or y1 <= 0:
        return None
    t = (xq - x0) / (x1 - x0)
    if t < 0 or t > 1:
        return None
    log_y = np.log10(y0) + t * (np.log10(y1) - np.log10(y0))
    return float(10 ** log_y)


def _apply_log_minor_ticks(axis) -> None:
    axis.set_minor_locator(LogLocator(base=10.0, subs=np.arange(2, 10) * 0.1))
    axis.set_minor_formatter(NullFormatter())


def _style_axes(ax, x_log: bool, y_log: bool) -> None:
    if x_log:
        ax.set_xscale("log")
        _apply_log_minor_ticks(ax.xaxis)
    if y_log:
        ax.set_yscale("log")
        _apply_log_minor_ticks(ax.yaxis)
    ax.grid(True, which="major", linewidth=RC_PARAMS["grid.linewidth"], alpha=RC_PARAMS["grid.alpha"])


def _resolve_limits(auto_min: Optional[float], auto_max: Optional[float], limits: Optional[dict]) -> tuple[Optional[float], Optional[float]]:
    if not limits:
        return auto_min, auto_max
    lo = limits.get("min")
    hi = limits.get("max")
    return (lo if lo is not None else auto_min, hi if hi is not None else auto_max)


# ---------------------------------------------------------------------------
# Simulation Chart -- X = Injection Rate (linear), Y = Acid Volume (log)
# ---------------------------------------------------------------------------

@dataclass
class SimCurveData:
    label: str
    color: str
    flowratepoints: Sequence[float]
    acidvolumepoints: Sequence[Optional[float]]
    q_opt: Optional[float] = None
    validity_min: Optional[float] = None
    validity_max: Optional[float] = None


def _split_validity(fps: Sequence[float], vals: Sequence[Optional[float]], vmin: Optional[float], vmax: Optional[float]):
    """Separa os pontos em dentro/fora da janela [vmin,vmax] de q -- mesma
    ideia de tools/validityWindow.ts (splitByValidity), replicada aqui so
    pra desenho (o corte fisico ja veio pronto no metadata do payload)."""
    xs = [x for x in fps]
    ys = [None if v is None else float(v) for v in vals]
    if vmin is None or vmax is None:
        return xs, ys, [None] * len(xs)
    inside = [(x >= vmin and x <= vmax) for x in xs]
    return xs, ys, inside


def _draw_simulation_curve(ax, curve: SimCurveData, show_band: bool) -> None:
    xs = list(curve.flowratepoints)
    ys = [None if v is None else float(v) for v in curve.acidvolumepoints]
    if not xs:
        return

    has_window = curve.validity_min is not None and curve.validity_max is not None
    if has_window:
        inside = [curve.validity_min <= x <= curve.validity_max for x in xs]
    else:
        inside = [True] * len(xs)

    # Segmenta em trechos contiguos dentro/fora pra alternar solido/tracejado
    # sem religar pontos que passam por None (clipped).
    n = len(xs)
    i = 0
    plotted_label = False
    while i < n:
        j = i
        cur_inside = inside[i]
        seg_x, seg_y = [], []
        while j < n and inside[j] == cur_inside:
            if ys[j] is not None:
                seg_x.append(xs[j])
                seg_y.append(ys[j])
            else:
                break
            j += 1
        if len(seg_x) >= 1:
            style = dict(color=curve.color if cur_inside else OUT_OF_WINDOW_GRAY, linewidth=RC_PARAMS["lines.linewidth"])
            if not cur_inside:
                style["linestyle"] = (0, (4, 2))
            ax.plot(seg_x, seg_y, label=(curve.label if (cur_inside and not plotted_label) else None), **style)
            if cur_inside:
                plotted_label = True
        i = max(j, i + 1)

    if show_band and has_window:
        xmin_plot, xmax_plot = min(xs), max(xs)
        if curve.validity_min > xmin_plot:
            ax.axvspan(xmin_plot, curve.validity_min, color=OUT_OF_WINDOW_GRAY, alpha=OUT_OF_WINDOW_BAND_ALPHA, lw=0)
        if curve.validity_max < xmax_plot:
            ax.axvspan(curve.validity_max, xmax_plot, color=OUT_OF_WINDOW_GRAY, alpha=OUT_OF_WINDOW_BAND_ALPHA, lw=0)

    if curve.q_opt is not None:
        for k in range(n - 1):
            x0, x1 = xs[k], xs[k + 1]
            if ys[k] is None or ys[k + 1] is None:
                continue
            if min(x0, x1) <= curve.q_opt <= max(x0, x1):
                y_at_opt = _interp_log_y(x0, ys[k], x1, ys[k + 1], curve.q_opt)
                if y_at_opt is not None:
                    ax.plot([curve.q_opt], [y_at_opt], marker="o", markersize=4, color=curve.color, markeredgecolor="white", markeredgewidth=0.5, zorder=5)
                break


def render_simulation_figure(
    curves: Sequence[SimCurveData],
    size: FigureSize = "single",
    show_validity_band: bool = True,
    show_optimum_path: bool = False,
    x_limits: Optional[dict] = None,
    y_limits: Optional[dict] = None,
) -> bytes:
    fig = build_simulation_figure(curves, size, show_validity_band, show_optimum_path, x_limits, y_limits)
    return _savefig_png(fig)


def build_simulation_figure(
    curves: Sequence[SimCurveData],
    size: FigureSize = "single",
    show_validity_band: bool = True,
    show_optimum_path: bool = False,
    x_limits: Optional[dict] = None,
    y_limits: Optional[dict] = None,
) -> Figure:
    """Mesma logica de render_simulation_figure, mas devolve a Figure (nao o
    PNG) -- usado por testes (pytest-mpl / comparacao de imagem baseline)."""
    with matplotlib.rc_context(RC_PARAMS):
        fig, canvas = _new_figure(size)
        ax = fig.add_subplot(111)

        for c in curves:
            _draw_simulation_curve(ax, c, show_validity_band)

        if show_optimum_path:
            # So conecta os q_opt JA MARCADOS por curva (interpolacao
            # geometrica em cima do dado existente, mesma _interp_log_y de
            # cada marcador individual) -- nao e uma curva nova calculada.
            opt_points: list[tuple[float, float]] = []
            for c in curves:
                if c.q_opt is None:
                    continue
                xs, ys = list(c.flowratepoints), list(c.acidvolumepoints)
                for k in range(len(xs) - 1):
                    if ys[k] is None or ys[k + 1] is None:
                        continue
                    if min(xs[k], xs[k + 1]) <= c.q_opt <= max(xs[k], xs[k + 1]):
                        y_opt = _interp_log_y(xs[k], ys[k], xs[k + 1], ys[k + 1], c.q_opt)
                        if y_opt is not None:
                            opt_points.append((c.q_opt, y_opt))
                        break
            if len(opt_points) > 1:
                opt_points.sort(key=lambda p: p[0])
                ax.plot(
                    [p[0] for p in opt_points], [p[1] for p in opt_points],
                    color=OPTIMUM_PATH_COLOR, linestyle=(0, (4, 2)), linewidth=1.6,
                    label="Optimum path", zorder=4,
                )

        # Y em decadas, so com pontos DENTRO da janela de validade (pedido
        # explicito) -- se nenhuma curva tiver janela, usa todos os pontos.
        in_window_ys: list[float] = []
        any_window = any(c.validity_min is not None for c in curves)
        for c in curves:
            for x, y in zip(c.flowratepoints, c.acidvolumepoints):
                if y is None or y <= 0:
                    continue
                if any_window and c.validity_min is not None and c.validity_max is not None:
                    if not (c.validity_min <= x <= c.validity_max):
                        continue
                in_window_ys.append(float(y))
        auto_ymin, auto_ymax = (min(in_window_ys), max(in_window_ys)) if in_window_ys else (None, None)
        if auto_ymin is not None:
            auto_ymin, auto_ymax = _decade_round(auto_ymin, auto_ymax)

        ymin, ymax = _resolve_limits(auto_ymin, auto_ymax, y_limits)
        xmin, xmax = _resolve_limits(None, None, x_limits)

        ax.set_xlabel("Injection Rate, gal/(ft·min)")
        ax.set_ylabel("Acid Volume, gal/ft")
        _style_axes(ax, x_log=False, y_log=True)
        if xmin is not None or xmax is not None:
            ax.set_xlim(left=xmin, right=xmax)
        if ymin is not None or ymax is not None:
            ax.set_ylim(bottom=ymin, top=ymax)

        if len(curves) > 1 or (curves and curves[0].label):
            ax.legend(loc="best", frameon=False, ncol=2 if size == "double" else 1)

        fig.tight_layout(pad=0.3)
        return fig


# ---------------------------------------------------------------------------
# Design Plot -- Y = Wormhole Length (log, espelhado), X-bottom = Rate (log),
# X-top (twiny) = Volume (log). Os dois eixos X cobrem o MESMO numero de
# decadas (mesma regra que Chart.tsx aplica no grafico interativo).
# ---------------------------------------------------------------------------

@dataclass
class DesignSeriesData:
    label: str
    color: str
    optimum_rate_series: Sequence[Sequence[float]]  # [[rate, length], ...]
    optimum_volume_series: Sequence[Sequence[float]]  # [[volume, length], ...]


def _design_axis_extents(all_series: Sequence[DesignSeriesData]):
    all_rates = [pt[0] for s in all_series for pt in s.optimum_rate_series]
    all_vols = [pt[0] for s in all_series for pt in s.optimum_volume_series]
    all_lengths = [pt[1] for s in all_series for pt in s.optimum_rate_series]

    rate_min = min(all_rates) if all_rates else 0.02
    rate_max = max(all_rates) if all_rates else 2000
    vol_min = min(all_vols) if all_vols else 0.01
    vol_max = max(all_vols) if all_vols else 1000
    length_min = min(all_lengths) if all_lengths else 1
    length_max = max(all_lengths) if all_lengths else 20

    y_axis_min, y_axis_max = _decade_round(length_min, length_max)

    dec_rate = np.log10(rate_max / rate_min) if rate_min > 0 else 1
    dec_vol = np.log10(vol_max / vol_min) if vol_min > 0 else 1
    w = dec_rate + dec_vol + 0.5 if np.isfinite(dec_rate) and np.isfinite(dec_vol) and dec_rate >= 0 and dec_vol >= 0 else 1
    w_int = int(np.ceil(w))

    rate_axis_min = 10 ** np.floor(np.log10(rate_min)) if rate_min > 0 else rate_min
    vol_axis_max = 10 ** np.ceil(np.log10(vol_max)) if vol_max > 0 else vol_max
    rate_axis_max = rate_axis_min * (10 ** w_int)
    vol_axis_min = vol_axis_max / (10 ** w_int)

    return {
        "y_min": y_axis_min, "y_max": y_axis_max,
        "rate_min": float(rate_axis_min), "rate_max": float(rate_axis_max),
        "vol_min": float(vol_axis_min), "vol_max": float(vol_axis_max),
    }


def render_design_figure(
    series_list: Sequence[DesignSeriesData],
    size: FigureSize = "single",
    x_limits: Optional[dict] = None,  # aplica so ao eixo de Rate (inferior)
    y_limits: Optional[dict] = None,  # aplica aos dois eixos Y (espelhados)
) -> bytes:
    fig = build_design_figure(series_list, size, x_limits, y_limits)
    return _savefig_png(fig)


def build_design_figure(
    series_list: Sequence[DesignSeriesData],
    size: FigureSize = "single",
    x_limits: Optional[dict] = None,
    y_limits: Optional[dict] = None,
) -> Figure:
    with matplotlib.rc_context(RC_PARAMS):
        fig, canvas = _new_figure(size)
        ax_rate = fig.add_subplot(111)
        ax_vol = ax_rate.twiny()
        ax_length_right = ax_rate.twinx()

        ext = _design_axis_extents(series_list)

        for s in series_list:
            rate_x = [pt[0] for pt in s.optimum_rate_series]
            rate_y = [pt[1] for pt in s.optimum_rate_series]
            ax_rate.plot(rate_x, rate_y, color=s.color, linewidth=RC_PARAMS["lines.linewidth"], linestyle="solid", label=s.label)

            vol_x = [pt[0] for pt in s.optimum_volume_series]
            vol_y = [pt[1] for pt in s.optimum_volume_series]
            ax_vol.plot(vol_x, vol_y, color=s.color, linewidth=RC_PARAMS["lines.linewidth"], linestyle=(0, (4, 2)))

        y_min, y_max = _resolve_limits(ext["y_min"], ext["y_max"], y_limits)
        rate_min, rate_max = _resolve_limits(ext["rate_min"], ext["rate_max"], x_limits)
        # Volume (topo) NUNCA le X Limits (pedido explicito) -- so decada-
        # arredondado do dado, sempre.
        vol_min, vol_max = ext["vol_min"], ext["vol_max"]

        ax_rate.set_xlabel("Optimum Injection Rate, gal/(ft·min)")
        ax_rate.set_ylabel("Wormhole Length, ft")
        ax_vol.set_xlabel("Acid Volume @ Optimum Rate, gal/ft")

        _style_axes(ax_rate, x_log=True, y_log=True)
        _style_axes(ax_vol, x_log=True, y_log=False)
        ax_length_right.set_yscale("log")
        _apply_log_minor_ticks(ax_length_right.yaxis)
        ax_length_right.set_ylabel("Wormhole Length, ft")

        ax_rate.set_xlim(rate_min, rate_max)
        ax_vol.set_xlim(vol_min, vol_max)
        ax_rate.set_ylim(y_min, y_max)
        ax_length_right.set_ylim(y_min, y_max)

        if len(series_list) > 1:
            ax_rate.legend(loc="best", frameon=False, ncol=2 if size == "double" else 1)

        fig.tight_layout(pad=0.3)
        return fig


# ---------------------------------------------------------------------------
# Skin Evolution -- X = Acid Volume (log), Y = Skin (linear, max 0)
# ---------------------------------------------------------------------------

@dataclass
class SkinSeriesData:
    label: str
    color: str
    points: Sequence[tuple[float, float]]  # (volume, skin)


def render_skin_figure(
    series_list: Sequence[SkinSeriesData],
    size: FigureSize = "single",
    x_limits: Optional[dict] = None,
    y_limits: Optional[dict] = None,
) -> bytes:
    fig = build_skin_figure(series_list, size, x_limits, y_limits)
    return _savefig_png(fig)


def build_skin_figure(
    series_list: Sequence[SkinSeriesData],
    size: FigureSize = "single",
    x_limits: Optional[dict] = None,
    y_limits: Optional[dict] = None,
) -> Figure:
    with matplotlib.rc_context(RC_PARAMS):
        fig, canvas = _new_figure(size)
        ax = fig.add_subplot(111)

        all_x = [p[0] for s in series_list for p in s.points]
        auto_xmin, auto_xmax = _decade_round(min(all_x), max(all_x)) if all_x else (None, None)

        for s in series_list:
            xs = [p[0] for p in s.points]
            ys = [p[1] for p in s.points]
            ax.plot(xs, ys, color=s.color, linewidth=RC_PARAMS["lines.linewidth"], label=s.label)

        xmin, xmax = _resolve_limits(auto_xmin, auto_xmax, x_limits)
        ymin, ymax = _resolve_limits(None, 0.0, y_limits)

        ax.set_xlabel("Acid Volume, gal/ft")
        ax.set_ylabel("Skin")
        _style_axes(ax, x_log=True, y_log=False)
        if xmin is not None or xmax is not None:
            ax.set_xlim(left=xmin, right=xmax)
        ax.set_ylim(top=ymax, bottom=ymin)

        if len(series_list) > 1:
            ax.legend(loc="best", frameon=False, ncol=2 if size == "double" else 1)

        fig.tight_layout(pad=0.3)
        return fig
