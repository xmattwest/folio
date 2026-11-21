"""Pure-Python Dawn State / Warm Precision SVG chart and diagram builders.

Matches the exact visual language of shelltoho.me/pubs/inside-lfm3/ and
Project Afriat's Warm Precision cards: transparent SVG background, Parchment
(#F5EEDC) track bars with 2px Blue Slate (#2C3E50) structure strokes, Golden
Orange (#F39C12) single-focus accents, Heckbert nice ticks, Pareto scatter
frontiers, paired slopegraphs, and smooth cubic Bezier schematics.
"""

from __future__ import annotations

import html
import math
from typing import Any

from folio.ir import FigureSpec, ResolvedManuscript
from folio.tokens import (
    BLUE_SLATE,
    COPPER_DEEP,
    GOLDEN_ORANGE,
    IVORY,
    ONYX,
    PARCHMENT,
    RULE_COLOR,
    SAGE_DEEP,
    SAGE_GREEN,
    SLATE_DEEP,
    SLATE_MIST,
    FormatSpec,
    fmt_number,
)

ROLE_FILL: dict[str, str] = {
    "primary": BLUE_SLATE,
    "focus": GOLDEN_ORANGE,
    "secondary": SAGE_GREEN,
    "context": SLATE_MIST,
}

ROLE_STROKE: dict[str, str] = {
    "primary": BLUE_SLATE,
    "focus": BLUE_SLATE,  # Golden Orange always gets a 2px Blue Slate outline
    "secondary": SAGE_DEEP,
    "context": SLATE_MIST,
}

ROLE_TEXT: dict[str, str] = {
    "primary": BLUE_SLATE,
    "focus": COPPER_DEEP,
    "secondary": SAGE_DEEP,
    "context": SLATE_MIST,
}


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _fmt_val(val: float, fig: FigureSpec) -> str:
    style = "percent" if fig.y_unit == "%" else ("pp" if fig.y_unit == "pp" else "number")
    unit = "" if fig.y_unit in ("%", "pp") else fig.y_unit
    return fmt_number(val, FormatSpec(style=style, decimals=fig.y_decimals, unit=unit))


def _fmt_x(val: float, fig: FigureSpec) -> str:
    style = "percent" if fig.x_unit == "%" else "number"
    unit = "" if fig.x_unit == "%" else fig.x_unit
    return fmt_number(val, FormatSpec(style=style, decimals=fig.x_decimals, unit=unit))


def _nice_ticks(low: float, high: float, count: int = 4) -> list[float]:
    """Compute clean human-readable axis ticks (adapted from Warm Precision figures.py)."""
    if abs(high - low) < 1e-12:
        high = low + 1.0
    raw = (high - low) / max(1, count)
    magnitude = 10.0 ** math.floor(math.log10(abs(raw)))
    step = min((m * magnitude for m in (1.0, 2.0, 2.5, 5.0, 10.0) if m * magnitude >= raw - 1e-12), default=raw)
    start = math.floor(low / step) * step
    ticks: list[float] = []
    val = start
    while val <= high + step * 1e-9:
        ticks.append(round(val, 10))
        val += step
    if ticks[-1] < high - 1e-9:
        ticks.append(round(ticks[-1] + step, 10))
    return ticks


def _svg_open(w: int, h: int, fig_id: str, title: str, desc: str) -> list[str]:
    tid = f"svg-{_esc(fig_id)}-title"
    did = f"svg-{_esc(fig_id)}-desc"
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="{tid} {did}" '
        f'style="display:block;width:100%;height:auto;font-family:Inter,-apple-system,Arial,sans-serif;">',
        f"<title id=\"{tid}\">{_esc(title)}</title>",
        f"<desc id=\"{did}\">{_esc(desc)}</desc>",
    ]


def _render_bar(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    """Inside-LFM3 Warm Precision full-width Parchment track bars + bottom caliper."""
    series = fig.series[0]
    cats = [resolved.interpolate(c) for c in fig.categories]
    vals = [resolved.metric_value(v) for v in series.values]

    n = len(cats)
    w = 840
    pad_x = 4
    track_w = w - 2 * pad_x

    # If all values >= 0, use crisp inside-lfm3 Parchment track bars
    if min(vals, default=0.0) >= -1e-12:
        raw_max = fig.y_max if fig.y_max is not None else max(vals, default=1.0)
        if fig.y_unit == "%" and raw_max >= 85.0 and fig.y_max is None:
            v_max = 100.0
        elif fig.y_max is not None:
            v_max = float(fig.y_max)
        else:
            ticks = _nice_ticks(0.0, raw_max * 1.05, count=4)
            v_max = ticks[-1]
        if v_max <= 0:
            v_max = 1.0

        row_step = 54 if n >= 5 else 62
        top_y = 22
        caliper_y = top_y + n * row_step + 8
        h = caliper_y + 34

        parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))
        parts.append(f'<g font-family="Inter, Arial, sans-serif" font-size="14.5" fill="{ONYX}">')

        for idx, (cat, val) in enumerate(zip(cats, vals)):
            label_y = top_y + idx * row_step
            bar_y = label_y + 10
            bar_h = 17
            is_focus = fig.focus_index is not None and idx == fig.focus_index
            fill = GOLDEN_ORANGE if is_focus else ROLE_FILL.get(series.role, BLUE_SLATE)
            stroke = BLUE_SLATE if is_focus else ROLE_STROKE.get(series.role, BLUE_SLATE)
            val_col = COPPER_DEEP if is_focus else ONYX
            bw = max(0.0, min(track_w, (val / v_max) * track_w))

            parts.append(
                f'<text x="{pad_x}" y="{label_y}" text-anchor="start" font-weight="600" fill="{ONYX}">{_esc(cat)}</text>'
            )
            parts.append(
                f'<text x="{w - pad_x}" y="{label_y}" text-anchor="end" font-weight="600" fill="{val_col}" '
                f'style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(val, fig))}</text>'
            )
            parts.append(
                f'<rect x="{pad_x}" y="{bar_y}" width="{track_w:.1f}" height="{bar_h}" rx="2" '
                f'fill="{PARCHMENT}" stroke="{PARCHMENT}" stroke-width="2"/>'
            )
            if bw > 0.5:
                parts.append(
                    f'<rect x="{pad_x}" y="{bar_y}" width="{bw:.1f}" height="{bar_h}" rx="2" '
                    f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
                )

        if fig.reference_value is not None and 0.0 <= fig.reference_value <= v_max:
            rx = pad_x + (fig.reference_value / v_max) * track_w
            parts.append(
                f'<line x1="{rx:.1f}" y1="{top_y - 10}" x2="{rx:.1f}" y2="{caliper_y}" '
                f'stroke="{SLATE_MIST}" stroke-width="1.5" stroke-dasharray="5 4"/>'
            )
            if fig.reference_label:
                parts.append(
                    f'<text x="{rx + 6:.1f}" y="{top_y - 12}" font-size="12" font-weight="600" fill="{SLATE_MIST}">'
                    f'{_esc(fig.reference_label)}</text>'
                )

        # Bottom caliper rule (matching inside-lfm3 data-bar-scale)
        axis_lbl = resolved.interpolate(fig.y_label or series.label)
        parts.append(f'<polyline points="{pad_x},{caliper_y} {w - pad_x},{caliper_y}" fill="none" stroke="{BLUE_SLATE}" stroke-width="2"/>')
        parts.append(f'<polyline points="{pad_x},{caliper_y - 5} {pad_x},{caliper_y + 5}" fill="none" stroke="{BLUE_SLATE}" stroke-width="2"/>')
        parts.append(f'<polyline points="{w - pad_x},{caliper_y - 5} {w - pad_x},{caliper_y + 5}" fill="none" stroke="{BLUE_SLATE}" stroke-width="2"/>')
        parts.append(
            f'<text x="{pad_x}" y="{caliper_y + 26}" font-size="14" text-anchor="start" fill="{SLATE_DEEP}" '
            f'style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(0.0, fig))}</text>'
        )
        parts.append(
            f'<text x="{w * 0.5:.1f}" y="{caliper_y + 26}" font-size="14" text-anchor="middle" fill="{SLATE_DEEP}">{_esc(axis_lbl)}</text>'
        )
        parts.append(
            f'<text x="{w - pad_x}" y="{caliper_y + 26}" font-size="14" text-anchor="end" fill="{SLATE_DEEP}" '
            f'style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(v_max, fig))}</text>'
        )
        parts.append("</g></svg>")
        return "\n".join(parts)

    # Diverging bars (negative + positive values)
    row_h = 46
    pad_t, pad_b, pad_l, pad_r = 24, 34, 210, 100
    h = pad_t + n * row_h + pad_b
    ticks = _nice_ticks(min(vals), max(vals), count=4)
    v_min = fig.y_min if fig.y_min is not None else min(0.0, ticks[0])
    v_max = fig.y_max if fig.y_max is not None else max(0.0, ticks[-1])
    plot_w = w - pad_l - pad_r

    def x_px(v: float) -> float:
        return pad_l + ((v - v_min) / (v_max - v_min)) * plot_w

    zero_x = x_px(0.0)
    parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))
    parts.append(f'<line x1="{zero_x:.1f}" y1="{pad_t - 6}" x2="{zero_x:.1f}" y2="{h - pad_b}" stroke="{BLUE_SLATE}" stroke-width="2"/>')
    for idx, (cat, val) in enumerate(zip(cats, vals)):
        cy = pad_t + idx * row_h + row_h * 0.5
        x_val = x_px(val)
        bx = min(zero_x, x_val)
        bw = max(2.0, abs(x_val - zero_x))
        is_focus = fig.focus_index is not None and idx == fig.focus_index
        fill = GOLDEN_ORANGE if is_focus else ROLE_FILL.get(series.role, BLUE_SLATE)
        parts.append(f'<text x="{pad_l - 12}" y="{cy + 5:.1f}" text-anchor="end" fill="{ONYX}" font-size="14" font-weight="600">{_esc(cat)}</text>')
        parts.append(f'<rect x="{bx:.1f}" y="{cy - 11:.1f}" width="{bw:.1f}" height="22" rx="2" fill="{fill}" stroke="{BLUE_SLATE}" stroke-width="2"/>')
        lx = x_val + 8 if val >= 0 else x_val - 8
        anc = "start" if val >= 0 else "end"
        parts.append(f'<text x="{lx:.1f}" y="{cy + 5:.1f}" text-anchor="{anc}" fill="{ONYX}" font-size="14" font-weight="600">{_esc(_fmt_val(val, fig))}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def _render_grouped_bar(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    cats = [resolved.interpolate(c) for c in fig.categories]
    all_series = [(s, [resolved.metric_value(v) for v in s.values]) for s in fig.series]
    all_vals = [v for _, vs in all_series for v in vs]

    w, h = 840, 310
    pad_t, pad_b, pad_l, pad_r = 44, 44, 56, 16
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    raw_min = fig.y_min if fig.y_min is not None else min(0.0, min(all_vals, default=0.0))
    raw_max = fig.y_max if fig.y_max is not None else max(all_vals, default=1.0) * 1.12
    ticks = _nice_ticks(raw_min, raw_max, count=4)
    v_min = float(fig.y_min) if fig.y_min is not None else ticks[0]
    v_max = float(fig.y_max) if fig.y_max is not None else ticks[-1]
    if fig.y_min is not None and fig.y_max is not None:
        ticks = [v_min + (v_max - v_min) * (i / 4.0) for i in range(5)]

    def y_px(v: float) -> float:
        return pad_t + plot_h - ((v - v_min) / (v_max - v_min)) * plot_h

    parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))

    # Legend at top
    lx = pad_l
    for s, _ in all_series:
        fill = ROLE_FILL.get(s.role, BLUE_SLATE)
        stroke = ROLE_STROKE.get(s.role, BLUE_SLATE)
        parts.append(f'<rect x="{lx}" y="12" width="14" height="14" rx="2" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lbl = resolved.interpolate(s.label)
        parts.append(f'<text x="{lx + 20}" y="24" fill="{SLATE_DEEP}" font-size="13.5" font-weight="600">{_esc(lbl)}</text>')
        lx += 34 + len(lbl) * 7.8

    for tv in ticks:
        ty = y_px(tv)
        is_zero = abs(tv) < 1e-9
        stroke = BLUE_SLATE if is_zero else RULE_COLOR
        sw = 2 if is_zero else 1
        parts.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{w - pad_r}" y2="{ty:.1f}" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(
            f'<text x="{pad_l - 10}" y="{ty + 4:.1f}" text-anchor="end" fill="{SLATE_MIST}" '
            f'font-size="12.5" style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(tv, fig))}</text>'
        )

    n_cats = len(cats)
    n_ser = len(all_series)
    group_w = plot_w / max(1, n_cats)
    bar_w = min(44.0, (group_w * 0.68) / max(1, n_ser))
    zero_y = y_px(0.0)

    for c_idx, cat in enumerate(cats):
        gx = pad_l + c_idx * group_w + group_w * 0.5
        start_x = gx - (n_ser * bar_w + (n_ser - 1) * 8) * 0.5
        for s_idx, (s, vs) in enumerate(all_series):
            val = vs[c_idx]
            bx = start_x + s_idx * (bar_w + 8)
            yv = y_px(val)
            by = min(zero_y, yv)
            bh = max(2.0, abs(zero_y - yv))
            fill = ROLE_FILL.get(s.role, BLUE_SLATE)
            stroke = ROLE_STROKE.get(s.role, BLUE_SLATE)
            parts.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="2" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
            )
            ly = by - 7 if val >= 0 else by + bh + 15
            parts.append(
                f'<text x="{bx + bar_w * 0.5:.1f}" y="{ly:.1f}" text-anchor="middle" fill="{ONYX}" '
                f'font-size="12.5" font-weight="600" style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(val, fig))}</text>'
            )
        parts.append(f'<text x="{gx:.1f}" y="{h - 18}" text-anchor="middle" fill="{ONYX}" font-size="13.5" font-weight="600">{_esc(cat)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def _render_line(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    cats = [resolved.interpolate(c) for c in fig.categories]
    all_series = [(s, [resolved.metric_value(v) for v in s.values]) for s in fig.series]
    all_vals = [v for _, vs in all_series for v in vs]
    if fig.reference_value is not None:
        all_vals.append(fig.reference_value)

    w, h = 840, 330
    pad_t, pad_b, pad_l, pad_r = 24, 44, 56, 182
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    raw_min = fig.y_min if fig.y_min is not None else min(0.0, min(all_vals, default=0.0))
    raw_max = fig.y_max if fig.y_max is not None else max(all_vals, default=1.0) * 1.1
    ticks = _nice_ticks(raw_min, raw_max, count=4)
    v_min = float(fig.y_min) if fig.y_min is not None else ticks[0]
    v_max = float(fig.y_max) if fig.y_max is not None else ticks[-1]
    if fig.y_min is not None and fig.y_max is not None:
        ticks = [v_min + (v_max - v_min) * (i / 4.0) for i in range(5)]

    def x_px(i: int) -> float:
        if len(cats) <= 1:
            return pad_l + plot_w * 0.5
        return pad_l + (i / (len(cats) - 1)) * plot_w

    def y_px(v: float) -> float:
        return pad_t + plot_h - ((v - v_min) / (v_max - v_min)) * plot_h

    parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))

    for tv in ticks:
        ty = y_px(tv)
        is_zero = abs(tv - v_min) < 1e-9
        stroke = BLUE_SLATE if is_zero else RULE_COLOR
        sw = 2 if is_zero else 1
        parts.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{w - pad_r}" y2="{ty:.1f}" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(
            f'<text x="{pad_l - 10}" y="{ty + 4:.1f}" text-anchor="end" fill="{SLATE_MIST}" '
            f'font-size="12.5" style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(tv, fig))}</text>'
        )

    for i, cat in enumerate(cats):
        parts.append(f'<text x="{x_px(i):.1f}" y="{h - pad_b + 24}" text-anchor="middle" fill="{ONYX}" font-size="13" font-weight="600">{_esc(cat)}</text>')

    if fig.reference_value is not None:
        ry = y_px(fig.reference_value)
        parts.append(f'<line x1="{pad_l}" y1="{ry:.1f}" x2="{w - pad_r}" y2="{ry:.1f}" stroke="{SLATE_MIST}" stroke-width="1.5" stroke-dasharray="5 4"/>')
        if fig.reference_label:
            parts.append(f'<text x="{w - pad_r + 10}" y="{ry + 4:.1f}" fill="{SLATE_MIST}" font-size="12" font-weight="600">{_esc(fig.reference_label)}</text>')

    # Nudge right-side end labels so they never overlap
    raw_end_ys: list[tuple[int, float]] = [(idx, y_px(vs[-1])) for idx, (_, vs) in enumerate(all_series)]
    raw_end_ys.sort(key=lambda kv: kv[1])
    placed_ys = [y for _, y in raw_end_ys]
    for _ in range(12):
        for i in range(1, len(placed_ys)):
            if placed_ys[i] - placed_ys[i - 1] < 21.0:
                mid = 0.5 * (placed_ys[i] + placed_ys[i - 1])
                placed_ys[i - 1] = mid - 10.5
                placed_ys[i] = mid + 10.5
    label_y_map = {raw_end_ys[i][0]: placed_ys[i] for i in range(len(raw_end_ys))}

    for idx, (s, vs) in enumerate(all_series):
        stroke = COPPER_DEEP if s.role == "focus" else ROLE_FILL.get(s.role, BLUE_SLATE)
        sw = 3.2 if s.role == "focus" else 2.4
        pts = " ".join(f"{x_px(i):.1f},{y_px(v):.1f}" for i, v in enumerate(vs))
        parts.append(f'<polyline fill="none" stroke="{stroke}" stroke-width="{sw}" points="{pts}"/>')

        for i, v in enumerate(vs):
            cx, cy = x_px(i), y_px(v)
            fill = GOLDEN_ORANGE if s.role == "focus" else stroke
            ring = BLUE_SLATE if s.role == "focus" else IVORY
            r = 6.0 if s.role == "focus" else 4.8
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{ring}" stroke-width="2"/>')

        ly = label_y_map[idx]
        lbl = f"{resolved.interpolate(s.label)} ({_fmt_val(vs[-1], fig)})"
        parts.append(
            f'<text x="{w - pad_r + 12}" y="{ly + 4:.1f}" fill="{ROLE_TEXT.get(s.role, ONYX)}" '
            f'font-size="13" font-weight="600" style="font-variant-numeric:tabular-nums;">{_esc(lbl)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_slope(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    """Two-column paired slopegraph with direct left and right endpoint labels."""
    cats = [resolved.interpolate(c) for c in fig.categories]
    left_cat = cats[0] if cats else "Before"
    right_cat = cats[1] if len(cats) > 1 else "After"
    all_series = [(s, [resolved.metric_value(v) for v in s.values[:2]]) for s in fig.series]
    all_vals = [v for _, vs in all_series for v in vs]

    w, h = 680, 320
    pad_t, pad_b, x_left, x_right = 40, 36, 210, 470
    plot_h = h - pad_t - pad_b

    ticks = _nice_ticks(min(0.0, min(all_vals, default=0.0)), max(all_vals, default=1.0), count=4)
    v_min = float(fig.y_min) if fig.y_min is not None else ticks[0]
    v_max = float(fig.y_max) if fig.y_max is not None else ticks[-1]

    def y_px(v: float) -> float:
        return pad_t + plot_h - ((v - v_min) / (v_max - v_min)) * plot_h

    def _nudge(pairs: list[tuple[int, float]]) -> dict[int, float]:
        sp = sorted(pairs, key=lambda kv: kv[1])
        ys = [y for _, y in sp]
        for _ in range(10):
            for i in range(1, len(ys)):
                if ys[i] - ys[i - 1] < 20.0:
                    m = 0.5 * (ys[i] + ys[i - 1])
                    ys[i - 1], ys[i] = m - 10.0, m + 10.0
        return {sp[i][0]: ys[i] for i in range(len(sp))}

    l_map = _nudge([(i, y_px(vs[0])) for i, (_, vs) in enumerate(all_series)])
    r_map = _nudge([(i, y_px(vs[-1])) for i, (_, vs) in enumerate(all_series)])

    parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))
    parts.append(f'<line x1="{x_left}" y1="{pad_t - 8}" x2="{x_left}" y2="{h - pad_b}" stroke="{RULE_COLOR}" stroke-width="1.5"/>')
    parts.append(f'<line x1="{x_right}" y1="{pad_t - 8}" x2="{x_right}" y2="{h - pad_b}" stroke="{RULE_COLOR}" stroke-width="1.5"/>')
    parts.append(f'<text x="{x_left}" y="22" text-anchor="middle" fill="{SLATE_DEEP}" font-size="14" font-weight="600">{_esc(left_cat)}</text>')
    parts.append(f'<text x="{x_right}" y="22" text-anchor="middle" fill="{SLATE_DEEP}" font-size="14" font-weight="600">{_esc(right_cat)}</text>')

    for idx, (s, vs) in enumerate(all_series):
        y0, y1 = y_px(vs[0]), y_px(vs[-1])
        stroke = COPPER_DEEP if s.role == "focus" else ROLE_FILL.get(s.role, BLUE_SLATE)
        fill = GOLDEN_ORANGE if s.role == "focus" else stroke
        ring = BLUE_SLATE if s.role == "focus" else IVORY
        sw = 3.2 if s.role == "focus" else 2.2
        col = ROLE_TEXT.get(s.role, ONYX)
        lbl = resolved.interpolate(s.label)
        parts.append(f'<line x1="{x_left}" y1="{y0:.1f}" x2="{x_right}" y2="{y1:.1f}" stroke="{stroke}" stroke-width="{sw}"/>')
        parts.append(f'<circle cx="{x_left}" cy="{y0:.1f}" r="5.5" fill="{fill}" stroke="{ring}" stroke-width="2"/>')
        parts.append(f'<circle cx="{x_right}" cy="{y1:.1f}" r="5.5" fill="{fill}" stroke="{ring}" stroke-width="2"/>')
        parts.append(
            f'<text x="{x_left - 12}" y="{l_map[idx] + 4:.1f}" text-anchor="end" fill="{col}" font-size="13" font-weight="600" '
            f'style="font-variant-numeric:tabular-nums;">{_esc(lbl)} · {_esc(_fmt_val(vs[0], fig))}</text>'
        )
        parts.append(
            f'<text x="{x_right + 12}" y="{r_map[idx] + 4:.1f}" text-anchor="start" fill="{col}" font-size="13" font-weight="600" '
            f'style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(vs[-1], fig))}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _render_scatter(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    """Inside-LFM3 (#fig-quant) Pareto frontier / storage-vs-performance scatter plot."""
    w, h = 840, 310
    pad_t, pad_b, pad_l, pad_r = 34, 48, 58, 22
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    pts: list[tuple[float, float, str, str, bool]] = []
    for s in fig.series:
        xs = [resolved.metric_value(x) for x in s.x_values]
        ys = [resolved.metric_value(y) for y in s.values]
        lbls = [resolved.interpolate(p) for p in s.point_labels] if s.point_labels else [resolved.interpolate(s.label)] * len(ys)
        for i, (xv, yv) in enumerate(zip(xs, ys)):
            is_focus = (fig.focus_index is not None and len(pts) == fig.focus_index) or s.role == "focus"
            pts.append((xv, yv, lbls[i] if i < len(lbls) else "", s.role, is_focus))

    all_x = [p[0] for p in pts] + ([fig.x_reference_value] if fig.x_reference_value is not None else [])
    all_y = [p[1] for p in pts] + ([fig.reference_value] if fig.reference_value is not None else [])
    raw_xt = _nice_ticks(fig.x_min if fig.x_min is not None else min(0.0, min(all_x, default=0.0)), fig.x_max if fig.x_max is not None else max(all_x, default=1.0) * 1.08, count=4)
    raw_yt = _nice_ticks(fig.y_min if fig.y_min is not None else min(0.0, min(all_y, default=0.0)), fig.y_max if fig.y_max is not None else max(all_y, default=1.0) * 1.12, count=4)
    xmin, xmax = (float(fig.x_min) if fig.x_min is not None else raw_xt[0]), (float(fig.x_max) if fig.x_max is not None else raw_xt[-1])
    ymin, ymax = (float(fig.y_min) if fig.y_min is not None else raw_yt[0]), (float(fig.y_max) if fig.y_max is not None else raw_yt[-1])
    x_ticks = [t for t in raw_xt if xmin - 1e-9 <= t <= xmax + 1e-9]
    y_ticks = [t for t in raw_yt if ymin - 1e-9 <= t <= ymax + 1e-9]

    def x_px(v: float) -> float:
        return pad_l + ((v - xmin) / (xmax - xmin)) * plot_w

    def y_px(v: float) -> float:
        return pad_t + plot_h - ((v - ymin) / (ymax - ymin)) * plot_h

    parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))
    if fig.y_label:
        parts.append(f'<text x="{pad_l}" y="18" fill="{ONYX}" font-size="13.5" font-weight="600">{_esc(resolved.interpolate(fig.y_label))}</text>')

    for yt in y_ticks:
        ty = y_px(yt)
        if abs(yt - ymin) < 1e-9:
            parts.append(f'<text x="{pad_l - 10}" y="{ty + 4:.1f}" text-anchor="end" fill="{SLATE_DEEP}" font-size="12.5" style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(yt, fig))}</text>')
            continue
        parts.append(f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{w - pad_r}" y2="{ty:.1f}" stroke="{SLATE_MIST}" stroke-width="1.2" stroke-dasharray="5 5" opacity="0.55"/>')
        parts.append(f'<text x="{pad_l - 10}" y="{ty + 4:.1f}" text-anchor="end" fill="{SLATE_DEEP}" font-size="12.5" style="font-variant-numeric:tabular-nums;">{_esc(_fmt_val(yt, fig))}</text>')

    parts.append(f'<line x1="{pad_l}" y1="{h - pad_b}" x2="{w - pad_r}" y2="{h - pad_b}" stroke="{BLUE_SLATE}" stroke-width="2"/>')
    for xt in x_ticks:
        tx = x_px(xt)
        parts.append(f'<text x="{tx:.1f}" y="{h - pad_b + 20}" text-anchor="middle" fill="{SLATE_DEEP}" font-size="12.5" style="font-variant-numeric:tabular-nums;">{_esc(_fmt_x(xt, fig))}</text>')

    if fig.x_label:
        parts.append(f'<text x="{pad_l + plot_w * 0.5:.1f}" y="{h - 5}" text-anchor="middle" fill="{ONYX}" font-size="13.5" font-weight="600">{_esc(resolved.interpolate(fig.x_label))}</text>')

    rx_val: float | None = None
    if fig.x_reference_value is not None:
        rx_val = x_px(fig.x_reference_value)
        parts.append(f'<line x1="{rx_val:.1f}" y1="{pad_t}" x2="{rx_val:.1f}" y2="{h - pad_b}" stroke="{COPPER_DEEP}" stroke-width="1.8" stroke-dasharray="6 4"/>')
        if fig.x_reference_label:
            parts.append(f'<text x="{rx_val + 9:.1f}" y="{pad_t + 13}" fill="{COPPER_DEEP}" font-size="12.5" font-weight="600">{_esc(resolved.interpolate(fig.x_reference_label))}</text>')

    for xv, yv, lbl, role, is_focus in pts:
        cx, cy = x_px(xv), y_px(yv)
        fill = GOLDEN_ORANGE if is_focus else ROLE_FILL.get(role, BLUE_SLATE)
        r = 7.5 if is_focus else 5.5
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{BLUE_SLATE}" stroke-width="2"/>')
        if lbl:
            near_right = cx > w - 190
            just_left_of_ref = rx_val is not None and 0.0 <= (rx_val - cx) <= 165.0 and (cx - pad_l) >= 135.0
            place_left = near_right or just_left_of_ref
            lx = cx - 12 if place_left else cx + 12
            anc = "end" if place_left else "start"
            ly = (cy - 6.0) if cy > (h - pad_b - 14.0) else (cy + 4.5)
            fw = "600" if is_focus else "500"
            col = COPPER_DEEP if is_focus else ONYX
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anc}" fill="{col}" font-size="13" font-weight="{fw}">{_esc(lbl)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def _render_schematic(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    """Clean Warm Precision architecture diagram with cubic S-curves and wide self-loops."""
    w, h = 840, 250
    parts = _svg_open(w, h, fig.id, resolved.interpolate(fig.title), resolved.interpolate(fig.alt))
    parts.append(
        f'<defs>'
        f'<marker id="arrow-{_esc(fig.id)}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 1 L 10 5 L 0 9 z" fill="{BLUE_SLATE}"/></marker>'
        f'<marker id="arrow-loop-{_esc(fig.id)}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 1 L 10 5 L 0 9 z" fill="{COPPER_DEEP}"/></marker>'
        f'</defs>'
    )

    node_map: dict[str, dict[str, Any]] = {str(n["id"]): n for n in fig.nodes}

    for edge in fig.edges:
        src = node_map.get(str(edge["from"]))
        dst = node_map.get(str(edge["to"]))
        if not src or not dst:
            continue
        dashed = ' stroke-dasharray="6 4"' if edge.get("dashed") else ""
        if edge.get("loop_back"):
            if str(edge["from"]) == str(edge["to"]):
                # Wide two-port feedback arc beneath the recurrent block
                lx1 = float(src["x"]) + float(src["w"]) * 0.74
                lx2 = float(src["x"]) + float(src["w"]) * 0.26
                ly = float(src["y"]) + float(src["h"])
                arc_y = ly + 56
                parts.append(
                    f'<path d="M {lx1:.1f} {ly:.1f} C {lx1 + 18:.1f} {arc_y:.1f}, {lx2 - 18:.1f} {arc_y:.1f}, {lx2:.1f} {ly + 3:.1f}" '
                    f'fill="none" stroke="{COPPER_DEEP}" stroke-width="2.4"{dashed} '
                    f'marker-end="url(#arrow-loop-{_esc(fig.id)})"/>'
                )
                if edge.get("label"):
                    elbl = resolved.interpolate(str(edge["label"]))
                    parts.append(
                        f'<text x="{(lx1 + lx2) * 0.5:.1f}" y="{arc_y + 12:.1f}" text-anchor="middle" '
                        f'fill="{COPPER_DEEP}" font-size="13" font-weight="600">{_esc(elbl)}</text>'
                    )
            else:
                lx1 = float(src["x"]) + float(src["w"]) * 0.5
                ly1 = float(src["y"]) + float(src["h"])
                lx2 = float(dst["x"]) + float(dst["w"]) * 0.5
                ly2 = float(dst["y"]) + float(dst["h"])
                mid_y = max(ly1, ly2) + 52
                parts.append(
                    f'<path d="M {lx1:.1f} {ly1:.1f} C {lx1:.1f} {mid_y:.1f}, {lx2:.1f} {mid_y:.1f}, {lx2:.1f} {ly2 + 3:.1f}" '
                    f'fill="none" stroke="{COPPER_DEEP}" stroke-width="2.2"{dashed} '
                    f'marker-end="url(#arrow-loop-{_esc(fig.id)})"/>'
                )
                if edge.get("label"):
                    elbl = resolved.interpolate(str(edge["label"]))
                    parts.append(
                        f'<text x="{(lx1 + lx2) * 0.5:.1f}" y="{mid_y + 12:.1f}" text-anchor="middle" '
                        f'fill="{COPPER_DEEP}" font-size="13" font-weight="600">{_esc(elbl)}</text>'
                    )
        else:
            x1 = float(src["x"]) + float(src["w"])
            y1 = float(src["y"]) + float(src["h"]) * 0.5
            x2 = float(dst["x"]) - 4.0
            y2 = float(dst["y"]) + float(dst["h"]) * 0.5
            if abs(y1 - y2) > 4.0:
                mx = 0.5 * (x1 + x2)
                parts.append(
                    f'<path d="M {x1:.1f} {y1:.1f} C {mx:.1f} {y1:.1f}, {mx:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" '
                    f'fill="none" stroke="{BLUE_SLATE}" stroke-width="2"{dashed} marker-end="url(#arrow-{_esc(fig.id)})"/>'
                )
            else:
                parts.append(
                    f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                    f'stroke="{BLUE_SLATE}" stroke-width="2"{dashed} marker-end="url(#arrow-{_esc(fig.id)})"/>'
                )
            if edge.get("label"):
                elbl = resolved.interpolate(str(edge["label"]))
                parts.append(
                    f'<text x="{(x1 + x2) * 0.5:.1f}" y="{(y1 + y2) * 0.5 - 8:.1f}" text-anchor="middle" '
                    f'fill="{SLATE_DEEP}" font-size="12.5" font-weight="600">{_esc(elbl)}</text>'
                )

    for n in fig.nodes:
        x, y, nw, nh = float(n["x"]), float(n["y"]), float(n["w"]), float(n["h"])
        role = str(n.get("role", "well"))
        if role == "focus":
            fill, stroke, text_col = GOLDEN_ORANGE, BLUE_SLATE, ONYX
        elif role == "structure":
            fill, stroke, text_col = BLUE_SLATE, BLUE_SLATE, IVORY
        elif role == "positive":
            fill, stroke, text_col = SAGE_GREEN, SAGE_DEEP, ONYX
        else:
            fill, stroke, text_col = PARCHMENT, BLUE_SLATE, ONYX

        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{nw:.1f}" height="{nh:.1f}" rx="8" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
        lbl = resolved.interpolate(str(n.get("label", "")))
        sub = resolved.interpolate(str(n.get("sublabel", "")))
        cy = y + nh * (0.41 if sub else 0.54)
        parts.append(
            f'<text x="{x + nw * 0.5:.1f}" y="{cy:.1f}" text-anchor="middle" fill="{text_col}" '
            f'font-size="14.5" font-weight="600">{_esc(lbl)}</text>'
        )
        if sub:
            sub_col = IVORY if role == "structure" else SLATE_DEEP
            parts.append(
                f'<text x="{x + nw * 0.5:.1f}" y="{cy + 20:.1f}" text-anchor="middle" fill="{sub_col}" '
                f'font-size="12.5" style="font-variant-numeric:tabular-nums;">{_esc(sub)}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def render_figure_svg(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    """Dispatch a declarative FigureSpec to its Dawn State SVG renderer."""
    if fig.kind == "bar":
        return _render_bar(fig, resolved)
    if fig.kind == "grouped_bar":
        return _render_grouped_bar(fig, resolved)
    if fig.kind == "line":
        return _render_line(fig, resolved)
    if fig.kind == "slope":
        return _render_slope(fig, resolved)
    if fig.kind == "scatter":
        return _render_scatter(fig, resolved)
    if fig.kind == "schematic":
        return _render_schematic(fig, resolved)
    raise ValueError(f"Unsupported figure kind '{fig.kind}' on figure '{fig.id}'")
