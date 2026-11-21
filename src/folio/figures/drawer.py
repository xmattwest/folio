"""Accessible <details> data drawers and shelltoho.me 4-part figure HTML blocks."""

from __future__ import annotations

import html
import struct
from pathlib import Path

from folio.figures.charts import _fmt_val, _fmt_x, render_figure_svg
from folio.ir import FigureSpec, ResolvedManuscript


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _read_image_dims(path: Path) -> tuple[int, int] | None:
    """Read intrinsic (width, height) from PNG or GIF headers without external deps."""
    if not path.is_file():
        return None
    head = path.read_bytes()[:24]
    if len(head) >= 24 and head[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", head[16:24])
        return int(w), int(h)
    if len(head) >= 10 and head[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", head[6:10])
        return int(w), int(h)
    return None


def render_figure_drawer_html(fig: FigureSpec, resolved: ResolvedManuscript) -> str:
    """Render the collapsible '<details class="figure-data"><summary>Text alternative and data</summary>' block."""
    title_text = resolved.interpolate(fig.title)
    alt_text = resolved.interpolate(fig.alt)
    rows_html: list[str] = []

    if fig.kind == "scatter" and fig.series:
        th_cells = (
            f'<th scope="col">Point</th>'
            f'<th scope="col" class="num">{_esc(resolved.interpolate(fig.x_label or "X"))}</th>'
            f'<th scope="col" class="num">{_esc(resolved.interpolate(fig.y_label or "Y"))}</th>'
        )
        for s in fig.series:
            lbls = [resolved.interpolate(p) for p in s.point_labels] if s.point_labels else [resolved.interpolate(s.label)] * len(s.values)
            for idx, (xv, yv) in enumerate(zip(s.x_values, s.values)):
                rx = resolved.metric_value(xv)
                ry = resolved.metric_value(yv)
                plbl = lbls[idx] if idx < len(lbls) else ""
                rows_html.append(
                    f"<tr><th scope=\"row\">{_esc(plbl)}</th>"
                    f'<td class="num">{_esc(_fmt_x(rx, fig))}</td>'
                    f'<td class="num">{_esc(_fmt_val(ry, fig))}</td></tr>'
                )
        table_block = (
            '<div class="table-scroll" tabindex="0" role="region" aria-label="Supporting figure data">'
            f"<table><caption>{_esc(title_text)}</caption>"
            f"<thead><tr>{th_cells}</tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody></table></div>"
        )
    elif fig.series and fig.categories:
        headers = ["Condition"] + [resolved.interpolate(s.label) for s in fig.series]
        th_cells = "".join(
            f'<th scope="col"{" class=\"num\"" if idx > 0 else ""}>{_esc(h)}</th>'
            for idx, h in enumerate(headers)
        )
        for c_idx, cat in enumerate(fig.categories):
            tds = [f'<th scope="row">{_esc(resolved.interpolate(cat))}</th>']
            for s in fig.series:
                val = resolved.metric_value(s.values[c_idx])
                tds.append(f'<td class="num">{_esc(_fmt_val(val, fig))}</td>')
            rows_html.append(f"<tr>{''.join(tds)}</tr>")
        table_block = (
            '<div class="table-scroll" tabindex="0" role="region" aria-label="Supporting figure data">'
            f"<table><caption>{_esc(title_text)}</caption>"
            f"<thead><tr>{th_cells}</tr></thead>"
            f"<tbody>{''.join(rows_html)}</tbody></table></div>"
        )
    elif fig.nodes:
        body_rows = "".join(
            f'<tr><th scope="row">{_esc(resolved.interpolate(str(n.get("label", ""))))}</th>'
            f'<td>{_esc(resolved.interpolate(str(n.get("sublabel", ""))))}</td></tr>'
            for n in fig.nodes
        )
        table_block = (
            '<div class="table-scroll" tabindex="0" role="region" aria-label="Supporting figure data">'
            f"<table><caption>{_esc(title_text)}</caption>"
            '<thead><tr><th scope="col">Stage</th><th scope="col">Specification</th></tr></thead>'
            f"<tbody>{body_rows}</tbody></table></div>"
        )
    else:
        table_block = ""

    return (
        '<details class="figure-data">'
        "<summary>Text alternative and data</summary>"
        f'<p class="figure-alt-prose">{_esc(alt_text)}</p>'
        f"{table_block}"
        "</details>"
    )


def render_figure_block_html(
    fig: FigureSpec,
    resolved: ResolvedManuscript,
    figure_number: int | None = None,
    media_src: str | None = None,
) -> str:
    """Render a shelltoho.me / inside-lfm3 4-part web figure (SVG or verified media) with data drawer."""
    title = resolved.interpolate(fig.title)
    subtitle = resolved.interpolate(fig.subtitle)
    caption_raw = fig.caption or fig.note or fig.source
    caption = resolved.interpolate(caption_raw)
    source = resolved.interpolate(fig.source)
    caveat = resolved.interpolate(fig.caveat) if fig.caveat else ""

    prefix = f"Figure {figure_number}. " if figure_number is not None else ""
    tier_badge = ""
    if fig.tier in ("exploratory", "negative") and figure_number is not None:
        tier_badge = f'<span class="tier-tag tier-{_esc(fig.tier)}">{_esc(fig.tier.upper())}</span> '

    drawer = render_figure_drawer_html(fig, resolved)

    cap_parts = [_esc(caption)]
    if fig.caption and fig.source and fig.source != fig.caption:
        cap_parts.append(_esc(source))
    elif fig.note and fig.source and fig.source != fig.note:
        cap_parts.append(_esc(source))
    if caveat:
        cap_parts.append(f"<strong>Scope:</strong> {_esc(caveat)}")

    if fig.kind == "media":
        src = media_src or f"assets/{Path(fig.media_path).name}"
        alt = resolved.interpolate(fig.alt)
        dims = _read_image_dims((resolved.ir.base_dir / fig.media_path).resolve())
        dim_attrs = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
        num_lead = f"<strong>{_esc(prefix.strip())}</strong> · " if prefix else ""
        return (
            f'<figure class="media-figure" id="fig-{_esc(fig.id)}">'
            f'<img src="{_esc(src)}"{dim_attrs} decoding="async" alt="{_esc(alt)}">'
            f"<figcaption>{tier_badge}{num_lead}{' '.join(cap_parts)}</figcaption>"
            f"{drawer}"
            f"</figure>"
        )

    svg = render_figure_svg(fig, resolved)
    return (
        f'<figure id="fig-{_esc(fig.id)}">'
        f'<p class="figure-title">{tier_badge}{_esc(prefix + title)}</p>'
        f'<p class="figure-subtitle">{_esc(subtitle)}</p>'
        f'<div class="figure-scroll" tabindex="0" role="region" aria-label="{_esc(fig.id)} figure; scroll horizontally on narrow screens">{svg}</div>'
        f"{drawer}"
        f"<figcaption>{' '.join(cap_parts)}</figcaption>"
        f"</figure>"
    )
