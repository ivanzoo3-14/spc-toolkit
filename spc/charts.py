"""spc.charts -- control-chart rendering with no third-party dependency.

The SVG writer is hand-rolled: an SVG file is just text, so a chart costs nothing at runtime and
works on a machine with no numpy, no matplotlib and no internet. If matplotlib happens to be
installed, `write_png` will optionally use it; if not, it says so and does nothing.

An SPC chart is not decoration. It is the artefact a quality engineer looks at to decide whether a
process is in control, so the limits are drawn where the statistics put them and points that break a
Nelson rule are marked.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .core import Chart

WIDTH = 900
HEIGHT = 380
PAD_L = 78
PAD_R = 24
PAD_T = 42
PAD_B = 46

_COLOURS = {
    "bg": "#ffffff",
    "grid": "#e6e6e6",
    "axis": "#666666",
    "limit": "#c0392b",
    "centre": "#1e8449",
    "line": "#1f3b63",
    "point": "#2c3e50",
    "bad": "#c0392b",
    "text": "#222222",
    "muted": "#777777",
}

_TITLES = {
    "individuals": "Individuals (I) chart",
    "moving_range": "Moving range (MR) chart",
    "xbar": "X-bar chart",
    "range": "R chart",
}


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def control_chart_svg(chart: Chart, title: Optional[str] = None, units: str = "",
                      subtitle: str = "") -> str:
    """Render one control chart as SVG text."""
    pts = list(chart.points)
    if not pts:
        raise ValueError("nothing to plot")
    title = title or _TITLES.get(chart.kind, chart.kind)

    lo = min(min(pts), chart.lcl)
    hi = max(max(pts), chart.ucl)
    if hi == lo:                      # constant data: invent a window so the lines are visible
        lo, hi = lo - 1.0, hi + 1.0
    span_pad = (hi - lo) * 0.12
    lo -= span_pad
    hi += span_pad

    plot_w = WIDTH - PAD_L - PAD_R
    plot_h = HEIGHT - PAD_T - PAD_B

    def x_at(i: int) -> float:
        if len(pts) == 1:
            return PAD_L + plot_w / 2.0
        return PAD_L + plot_w * i / (len(pts) - 1)

    def y_at(v: float) -> float:
        return PAD_T + plot_h * (hi - v) / (hi - lo)

    bad_idx = {i for _rule, i, _txt in chart.violations if 0 <= i < len(pts)}

    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="{_esc(title)}">',
        f'<rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" fill="{_COLOURS["bg"]}"/>',
        f'<text x="{PAD_L}" y="24" font-family="Segoe UI,Arial,sans-serif" font-size="16" '
        f'font-weight="600" fill="{_COLOURS["text"]}">{_esc(title)}</text>',
    ]
    if subtitle:
        parts.append(
            f'<text x="{PAD_L}" y="40" font-family="Segoe UI,Arial,sans-serif" font-size="11" '
            f'fill="{_COLOURS["muted"]}">{_esc(subtitle)}</text>')

    # horizontal gridlines for the centre line and limits, each labelled on the left
    for value, label, colour, dash in (
        (chart.ucl, "UCL", _COLOURS["limit"], ' stroke-dasharray="6 4"'),
        (chart.center, "CL", _COLOURS["centre"], ""),
        (chart.lcl, "LCL", _COLOURS["limit"], ' stroke-dasharray="6 4"'),
    ):
        y = y_at(value)
        parts.append(f'<line x1="{PAD_L}" y1="{y:.2f}" x2="{WIDTH - PAD_R}" y2="{y:.2f}" '
                     f'stroke="{colour}" stroke-width="1.4"{dash}/>')
        parts.append(f'<text x="{PAD_L - 8}" y="{y + 4:.2f}" text-anchor="end" '
                     f'font-family="Segoe UI,Arial,sans-serif" font-size="11" fill="{colour}">'
                     f'{label} {value:.4g}</text>')

    # axes
    parts.append(f'<line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{WIDTH - PAD_R}" '
                 f'y2="{PAD_T + plot_h}" stroke="{_COLOURS["axis"]}" stroke-width="1"/>')
    parts.append(f'<text x="{PAD_L}" y="{HEIGHT - 14}" font-family="Segoe UI,Arial,sans-serif" '
                 f'font-size="11" fill="{_COLOURS["muted"]}">'
                 f'sample 1 .. {len(pts)}{(" (" + units + ")") if units else ""}</text>')

    # the trace
    if len(pts) > 1:
        d = " ".join(f"{x_at(i):.2f},{y_at(v):.2f}" for i, v in enumerate(pts))
        parts.append(f'<polyline points="{d}" fill="none" stroke="{_COLOURS["line"]}" '
                     f'stroke-width="1.6"/>')

    # the points
    for i, v in enumerate(pts):
        bad = i in bad_idx
        r = 4.0 if bad else 2.8
        colour = _COLOURS["bad"] if bad else _COLOURS["point"]
        parts.append(f'<circle cx="{x_at(i):.2f}" cy="{y_at(v):.2f}" r="{r}" fill="{colour}">'
                     f'<title>sample {i + 1}: {v:.6g}</title></circle>')

    if bad_idx:
        parts.append(
            f'<text x="{WIDTH - PAD_R}" y="24" text-anchor="end" '
            f'font-family="Segoe UI,Arial,sans-serif" font-size="11" fill="{_COLOURS["bad"]}">'
            f'{len(bad_idx)} point(s) flagged by a Nelson rule</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def write_svg(path: str, chart: Chart, title: Optional[str] = None, units: str = "",
              subtitle: str = "") -> str:
    svg = control_chart_svg(chart, title=title, units=units, subtitle=subtitle)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return path


def write_png(path: str, chart: Chart, title: Optional[str] = None) -> Optional[str]:
    """Optional PNG via matplotlib. Returns None (and prints why) if matplotlib is absent."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("  (PNG skipped: matplotlib is not installed. The SVG chart was still written.)")
        return None

    title = title or _TITLES.get(chart.kind, chart.kind)
    fig, ax = plt.subplots(figsize=(9.0, 3.8), dpi=140)
    xs = list(range(1, len(chart.points) + 1))
    ax.plot(xs, chart.points, "-o", color=_COLOURS["line"], ms=3.5, lw=1.4)
    ax.axhline(chart.center, color=_COLOURS["centre"], lw=1.2, label=f"CL {chart.center:.4g}")
    for value, label in ((chart.ucl, "UCL"), (chart.lcl, "LCL")):
        ax.axhline(value, color=_COLOURS["limit"], lw=1.2, ls="--", label=f"{label} {value:.4g}")
    bad_idx = {i for _r, i, _t in chart.violations}
    if bad_idx:
        ax.plot([xs[i] for i in sorted(bad_idx)], [chart.points[i] for i in sorted(bad_idx)],
                "o", color=_COLOURS["bad"], ms=6, label="rule violation")
    ax.set_title(title, loc="left", fontsize=12, fontweight="600")
    ax.set_xlabel("sample")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path
