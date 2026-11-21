"""Target 3: Substack Paste-Ready 680px Charter HTML + 2x PNG figure package.

Matches Project Afriat's runs/social_cards/substack_paste_ready.html (the source
behind https://shelltoho.me/pubs/money-is-moral/): clean narrative paragraphs,
vivid blockquotes, <figure><img><figcaption> pointing to 2x Retina PNG cards,
and zero inline <svg>, <details>, or spreadsheet bullet dumps.
"""

from __future__ import annotations

from folio.ir import ResolvedManuscript
from folio.render.common import esc, render_blockquote_html, render_inline_md

SUBSTACK_CSS = """
body {
  max-width: 680px;
  margin: 48px auto;
  padding: 0 24px 80px;
  font-family: Charter, 'Bitstream Charter', 'Sitka Text', Cambria, Georgia, serif;
  font-size: 19px;
  line-height: 1.65;
  color: #1f1f1f;
  background: #ffffff;
}
.meta-box {
  background: #f7f5f0;
  border: 1px solid #e2ddd2;
  border-radius: 8px;
  padding: 18px 22px;
  margin-bottom: 36px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 15px;
  line-height: 1.5;
}
.meta-box p { margin: 6px 0; }
.meta-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #7a6f5d;
}
h2 {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.25;
  margin: 44px 0 16px;
  color: #111111;
}
h3 {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.3;
  margin: 32px 0 12px;
  color: #1f1f1f;
}
p { margin: 0 0 20px; }
ul, ol { margin: 0 0 24px; padding-left: 26px; }
li { margin-bottom: 10px; }
blockquote {
  border-left: 3px solid #f39c12;
  margin: 24px 0;
  padding: 6px 0 6px 20px;
  color: #2b2b2b;
}
blockquote p { margin: 0 0 10px; }
blockquote p:last-child { margin-bottom: 0; }
figure { margin: 32px 0; }
img { max-width: 100%; height: auto; display: block; border-radius: 4px; }
figcaption {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.45;
  color: #666666;
  margin-top: 8px;
  text-align: center;
}
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.86em;
  background: #f3f2ee;
  padding: 2px 5px;
  border-radius: 4px;
}
hr {
  border: none;
  border-top: 1px solid #e5e5e5;
  margin: 40px 0;
}
a { color: #b85d19; text-decoration: underline; }
"""


def render_substack(
    resolved: ResolvedManuscript,
    figure_png_paths: dict[str, str],
    asset_base_url: str = "",
) -> str:
    """Compile a ResolvedManuscript into Substack paste-ready 680px Charter HTML."""
    ir = resolved.ir
    meta = ir.meta
    title_a = resolved.interpolate(meta.monograph_title or meta.title)
    title_b = resolved.interpolate(meta.substack_title_alt) if meta.substack_title_alt else ""
    subtitle = resolved.interpolate(meta.subtitle or meta.lede)

    body_parts: list[str] = []
    if meta.opening_paragraphs:
        for p in meta.opening_paragraphs:
            body_parts.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")
    elif meta.lede:
        body_parts.append(f"<p>{render_inline_md(resolved.interpolate(meta.lede))}</p>")

    def _substack_fig_html(fid: str) -> str:
        fig = ir.figures[fid]
        rel_img = figure_png_paths.get(fid, f"figures/{fid}_2x.png")
        src = f"{asset_base_url.rstrip('/')}/{rel_img.lstrip('/')}" if asset_base_url else rel_img
        caption = resolved.interpolate(fig.caption or fig.title)
        alt = resolved.interpolate(fig.alt)
        return (
            "<figure>"
            f'<img src="{esc(src)}" alt="{esc(alt)}">'
            f"<figcaption>{esc(caption)}</figcaption>"
            "</figure>"
        )

    hero_fid = meta.hero_figure
    if hero_fid and hero_fid in ir.figures:
        body_parts.append(_substack_fig_html(hero_fid))

    for sec in ir.sections:
        if sec.hr_before:
            body_parts.append("<hr>")
        tag = "h3" if sec.level >= 3 else "h2"
        stitle = resolved.interpolate(sec.monograph_title)
        body_parts.append(f"<{tag}>{esc(stitle)}</{tag}>")

        for p in sec.paragraphs:
            body_parts.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")

        for q in sec.quotes:
            body_parts.append(render_blockquote_html(q, resolved))

        for eid in sec.equation_ids:
            eq = ir.equations[eid]
            body_parts.append(f"<blockquote><p><code>{esc(eq.unicode)}</code></p></blockquote>")

        for fid in sec.figure_ids:
            if fid == hero_fid:
                continue
            body_parts.append(_substack_fig_html(fid))

        if sec.bullets:
            lis = "".join(f"<li>{render_inline_md(resolved.interpolate(b))}</li>" for b in sec.bullets)
            body_parts.append(f"<ul>{lis}</ul>")

        for p in sec.post_paragraphs:
            body_parts.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")

        if sec.callout:
            body_parts.append(
                f"<blockquote><p>{render_inline_md(resolved.interpolate(sec.callout))}</p></blockquote>"
            )

        if meta.substack_tables:
            for tid in sec.table_ids:
                tbl = ir.tables[tid]
                t_title = resolved.interpolate(tbl.title)
                body_parts.append(f"<p><strong>{esc(t_title)}</strong></p>")
                items: list[str] = []
                for row in tbl.rows:
                    pairs = [
                        f"{resolved.interpolate(h)}: {resolved.interpolate(c)}"
                        for h, c in zip(tbl.headers[1:], row[1:])
                    ]
                    lead = resolved.interpolate(row[0]) if row else ""
                    items.append(f"<li><strong>{esc(lead)}</strong>: {render_inline_md(', '.join(pairs))}</li>")
                body_parts.append(f"<ul>{''.join(items)}</ul>")

    if meta.canonical_url:
        disp_url = meta.canonical_url.replace("https://", "").replace("http://", "").rstrip("/")
        body_parts.append(
            f'<p><em>Interactive web edition, full tables, and code by {esc(meta.author)} at '
            f'<a href="{esc(meta.canonical_url)}">{esc(disp_url)}</a>.</em></p>'
        )

    alt_title_html = f"<p><strong>Title Option B:</strong> {esc(title_b)}</p>" if title_b else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Terms of Plenty (Substack Paste-Ready) &middot; {esc(title_a)}</title>
<style>{SUBSTACK_CSS}</style>
</head>
<body>

<div class="meta-box">
  <p class="meta-label">Substack Header Fields (Paste Separately at Top of Editor)</p>
  <p><strong>Title Option A (Recommended):</strong> {esc(title_a)}</p>
  {alt_title_html}
  <p><strong>Subtitle:</strong> {esc(subtitle)}</p>
  <p style="color:#666; font-size:13px; margin-top:10px;">Tip: Open this file in Chrome, highlight everything <strong>below</strong> this box, copy (Cmd+C), and paste (Cmd+V) into the Substack post body.</p>
</div>

{"".join(body_parts)}

</body>
</html>
"""
