"""Target 2: shelltoho.me Essay / Visual Research Monograph renderer (money-is-moral & inside-lfm3 style)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from folio.figures.drawer import render_figure_block_html
from folio.ir import ResolvedManuscript
from folio.render.common import (
    READER_SCROLLSPY_JS,
    SHELLTOHO_EDITORIAL_CSS,
    build_sidebar_toc_html,
    esc,
    render_blockquote_html,
    render_inline_md,
    render_math_html,
    render_seo_head_html,
    render_table_html,
)
from folio.tokens import GOOGLE_FONTS_LINK


def _build_monograph_inner_html(
    resolved: ResolvedManuscript,
    *,
    media_prefix: str = "assets",
) -> tuple[str, str, str, str]:
    ir = resolved.ir
    meta = ir.meta
    page_title = resolved.interpolate(meta.monograph_title or meta.title)
    sidebar_sub = resolved.interpolate(meta.subtitle) if meta.subtitle else ""
    lede = resolved.interpolate(meta.lede) if meta.lede else ""

    byline_parts = [meta.author]
    if meta.affiliation:
        byline_parts.append(meta.affiliation)
    if meta.date:
        byline_parts.append(meta.date)
    byline = " \u00b7 ".join(p for p in byline_parts if p)

    def _fig_html(fid: str) -> str:
        fig = ir.figures[fid]
        msrc = f"{media_prefix.rstrip('/')}/{Path(fig.media_path).name}" if fig.kind == "media" else None
        return render_figure_block_html(fig, resolved, figure_number=None, media_src=msrc)

    opening_html_parts: list[str] = []
    if meta.opening_paragraphs:
        for p in meta.opening_paragraphs:
            opening_html_parts.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")
    elif lede:
        opening_html_parts.append(f'<p class="report-lede">{render_inline_md(lede)}</p>')

    if meta.opening_summary and not meta.opening_paragraphs:
        lis = "".join(
            f"<li>{render_inline_md(resolved.interpolate(item))}</li>" for item in meta.opening_summary
        )
        opening_html_parts.append(f'<div class="opening-summary"><ul>{lis}</ul></div>')

    hero_fid = meta.hero_figure
    if hero_fid and hero_fid in ir.figures:
        opening_html_parts.append(_fig_html(hero_fid))

    sections_html: list[str] = []
    for sec in ir.sections:
        stitle = resolved.interpolate(sec.monograph_title)
        tag = "h3" if sec.level >= 3 else "h2"
        block: list[str] = []
        if sec.hr_before:
            block.append("<hr>")
        block.append(f'<{tag} id="sec-{esc(sec.id)}">{esc(stitle)}</{tag}>')

        if sec.caveat:
            block.append(
                f'<p class="section-caveat"><strong>Scope note:</strong> '
                f"{render_inline_md(resolved.interpolate(sec.caveat))}</p>"
            )

        for p in sec.paragraphs:
            block.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")

        for q in sec.quotes:
            block.append(render_blockquote_html(q, resolved))

        for eid in sec.equation_ids:
            eq = ir.equations[eid]
            block.append(f'<div class="equation-block"><span>{render_math_html(eq.unicode)}</span></div>')

        for fid in sec.figure_ids:
            if fid == hero_fid:
                continue
            block.append(_fig_html(fid))

        for tid in sec.table_ids:
            tbl = ir.tables[tid]
            tbl_title = resolved.interpolate(tbl.title)
            block.append(
                f'<details class="table-drawer">'
                f"<summary>Full table: {esc(tbl_title)}</summary>"
                f"{render_table_html(tbl, resolved, table_number=None)}"
                f"</details>"
            )

        if sec.bullets:
            lis = "".join(f"<li>{render_inline_md(resolved.interpolate(b))}</li>" for b in sec.bullets)
            block.append(f"<ul>{lis}</ul>")

        for p in sec.post_paragraphs:
            block.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")

        if sec.callout:
            block.append(
                f'<div class="example-strip"><p>{render_inline_md(resolved.interpolate(sec.callout))}</p></div>'
            )

        sections_html.append("\n".join(block))

    art_rows = "".join(
        f'<tr><th scope="row"><code>{esc(alias)}</code></th>'
        f"<td><code>{esc(ir.artifacts[alias].path)}</code></td>"
        f"<td><code>{esc(digest[:16])}</code></td></tr>"
        for alias, digest in resolved.artifact_hashes.items()
    )
    disclosure = (
        f"<p>{render_inline_md(resolved.interpolate(meta.ai_disclosure))}</p>"
        if meta.ai_disclosure
        else ""
    )
    provenance_footer = (
        '<footer class="provenance-footer">'
        '<details class="figure-data">'
        f"<summary>Verified build receipt ({len(resolved.metrics)} bound claims across {len(resolved.artifact_hashes)} SHA-256 artifacts)</summary>"
        '<div class="table-scroll"><table>'
        '<thead><tr><th scope="col">Artifact</th><th scope="col">Path</th><th scope="col">SHA-256</th></tr></thead>'
        f"<tbody>{art_rows}</tbody>"
        "</table></div>"
        f"{disclosure}"
        "</details>"
        "</footer>"
    )

    inner = (
        '  <header class="report-header">\n'
        f"    <h1>{esc(page_title)}</h1>\n"
        f'    <p class="report-byline">{esc(byline)}</p>\n'
        "  </header>\n"
        f'  {"\n".join(opening_html_parts)}\n'
        f'  {"\n\n".join(sections_html)}\n'
        f"  {provenance_footer}"
    )
    return page_title, sidebar_sub, lede, inner


def render_monograph(resolved: ResolvedManuscript) -> str:
    """Compile a ResolvedManuscript into a standalone shelltoho.me/pubs/ essay HTML page."""
    ir = resolved.ir
    meta = ir.meta
    page_title, sidebar_sub, lede, inner = _build_monograph_inner_html(resolved, media_prefix="assets")
    desc = lede or sidebar_sub or page_title
    seo_head = render_seo_head_html(
        resolved,
        page_title=page_title,
        description=desc,
        url=meta.canonical_url,
        schema_type="ScholarlyArticle",
    )

    toc_html = build_sidebar_toc_html(
        ir.sections,
        resolved,
        use_preprint_titles=False,
    )
    status_html = f'<p class="reader-status">{esc(meta.monograph_status)}</p>' if meta.monograph_status else ""
    sub_html = f'<p class="reader-subtitle">{esc(sidebar_sub)}</p>' if sidebar_sub else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)} | {esc(meta.author)}</title>
{seo_head}
<link rel="stylesheet" href="{GOOGLE_FONTS_LINK}">
<style>{SHELLTOHO_EDITORIAL_CSS}</style>
</head>
<body class="lfm3-report money-is-moral">
<a class="reader-skip" href="#reader-manuscript">Skip to manuscript</a>
<aside class="reader-sidebar" aria-label="Preprint navigation">
  <a class="reader-home" href="{esc(meta.home_url)}">{esc(meta.home_label)}</a>
  <a class="reader-title" href="#reader-manuscript">{esc(page_title)}</a>
  {sub_html}{status_html}
  <details class="reader-contents" open>
    <summary>On this page <span aria-hidden="true">&#8964;</span></summary>
    <nav aria-label="Manuscript sections"><ul>{toc_html}</ul></nav>
  </details>
</aside>
<main class="lfm3-manuscript reader-page" id="reader-manuscript" tabindex="-1">
{inner}
</main>
<script type="module">{READER_SCROLLSPY_JS}</script>
</body>
</html>
"""


def render_shelltoho_source(resolved: ResolvedManuscript) -> str:
    """Emit a clean controlled-HTML manuscript source for shelltoho.me's renderPreprintReader."""
    meta = resolved.ir.meta
    if meta.canonical_url:
        parsed_path = urlparse(meta.canonical_url).path.rstrip("/")
        media_prefix = f"{parsed_path}/assets"
    else:
        media_prefix = "assets"
    page_title, sidebar_sub, lede, inner = _build_monograph_inner_html(resolved, media_prefix=media_prefix)
    desc = lede or sidebar_sub or page_title
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(page_title)} | {esc(meta.author)}</title>"
        f'<meta name="description" content="{esc(desc)}"></head>'
        '<body class="lfm3-report money-is-moral"><main class="lfm3-manuscript">\n'
        f"{inner}\n"
        "</main></body></html>\n"
    )
