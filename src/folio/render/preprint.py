"""Target 1: shelltoho.me Web Preprint / Quasi-Publication renderer (multiply-by-a-million style)."""

from __future__ import annotations

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


def render_preprint(resolved: ResolvedManuscript) -> str:
    """Compile a ResolvedManuscript into a shelltoho.me 8.5in sheet web preprint HTML page."""
    ir = resolved.ir
    meta = ir.meta
    page_title = resolved.interpolate(meta.preprint_title or meta.title)
    subtitle = resolved.interpolate(meta.subtitle) if meta.subtitle else ""

    byline_parts = [meta.author]
    if meta.affiliation:
        byline_parts.append(meta.affiliation)
    if meta.date:
        byline_parts.append(meta.date)
    byline = " \u00b7 ".join(p for p in byline_parts if p)

    # Assign academic section numbers (1, 2, 2.1, ...)
    numbered_map: dict[str, str] = {}
    h2_num = 0
    h3_num = 0
    for sec in ir.sections:
        if sec.level <= 2:
            h2_num += 1
            h3_num = 0
            num_str = f"{h2_num}"
        else:
            h3_num += 1
            num_str = f"{h2_num}.{h3_num}"
        numbered_map[sec.id] = num_str

    toc_html = build_sidebar_toc_html(
        ir.sections,
        resolved,
        use_preprint_titles=True,
        numbered_map=numbered_map,
        has_abstract=bool(meta.abstract),
        has_references=bool(ir.citations),
    )

    abstract_html = ""
    if meta.abstract:
        abstract_html = (
            '<section class="abstract-box" id="abstract">'
            "<h2>Abstract</h2>"
            f"<p>{render_inline_md(resolved.interpolate(meta.abstract))}</p>"
            "</section>"
        )

    fig_counter = 0
    tbl_counter = 0
    sections_html: list[str] = []
    for sec in ir.sections:
        num_str = numbered_map[sec.id]
        stitle = resolved.interpolate(sec.preprint_title)
        tag = "h3" if sec.level >= 3 else "h2"
        tier_badge = ""
        if sec.tier in ("exploratory", "negative"):
            tier_badge = f'<span class="tier-tag tier-{esc(sec.tier)}">{esc(sec.tier.upper())}</span> '

        block: list[str] = [
            f'<section id="sec-{esc(sec.id)}">',
            f'<{tag}>{tier_badge}{esc(num_str)} {esc(stitle)}</{tag}>',
        ]
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
            lbl_html = f'<span class="equation-label">({esc(eq.label)})</span>' if eq.label else ""
            block.append(
                f'<div class="equation-block" data-latex="{esc(eq.latex)}">'
                f"<span>{render_math_html(eq.unicode)}</span>{lbl_html}</div>"
            )
        for fid in sec.figure_ids:
            fig_counter += 1
            block.append(render_figure_block_html(ir.figures[fid], resolved, figure_number=fig_counter))
        for tid in sec.table_ids:
            tbl_counter += 1
            block.append(render_table_html(ir.tables[tid], resolved, table_number=tbl_counter))
        if sec.bullets:
            lis = "".join(f"<li>{render_inline_md(resolved.interpolate(b))}</li>" for b in sec.bullets)
            block.append(f"<ul>{lis}</ul>")
        for p in sec.post_paragraphs:
            block.append(f"<p>{render_inline_md(resolved.interpolate(p))}</p>")
        if sec.callout:
            block.append(f"<blockquote><p>{render_inline_md(resolved.interpolate(sec.callout))}</p></blockquote>")
        block.append("</section>")
        sections_html.append("\n".join(block))

    refs_html = ""
    if ir.citations:
        ref_lis = []
        for c in ir.citations:
            link = f' <a href="{esc(c.url)}" target="_blank" rel="noopener">{esc(c.url)}</a>' if c.url else ""
            venue = f" <em>{esc(c.venue)}</em>." if c.venue else ""
            ref_lis.append(
                f'<li id="ref-{esc(c.key)}">{esc(c.authors)} ({esc(c.year)}). '
                f"{esc(c.title)}.{venue}{link}</li>"
            )
        refs_html = (
            '<section id="references">'
            "<h2>References</h2>"
            f'<ol class="citations-list">{"".join(ref_lis)}</ol>'
            "</section>"
        )

    disclosure = (
        f"<p>{render_inline_md(resolved.interpolate(meta.ai_disclosure))}</p>"
        if meta.ai_disclosure
        else ""
    )
    repo_link = (
        f'<p>Repository: <a href="{esc(meta.repo_url)}" target="_blank" rel="noopener">{esc(meta.repo_url)}</a></p>'
        if meta.repo_url
        else ""
    )
    sub_html = f'<p class="reader-subtitle">{esc(subtitle)}</p>' if subtitle else ""
    status_html = f'<p class="reader-status">{esc(meta.preprint_status)}</p>' if meta.preprint_status else ""
    desc = resolved.interpolate(meta.abstract or meta.lede or meta.subtitle) if (meta.abstract or meta.lede or meta.subtitle) else page_title
    seo_head = render_seo_head_html(
        resolved,
        page_title=page_title,
        description=desc,
        url=meta.preprint_url or meta.canonical_url,
        schema_type="ScholarlyArticle",
    )

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
<body class="preprint-sheet">
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
<main class="reader-page" id="reader-manuscript" tabindex="-1">
  <header class="report-header">
    <h1>{esc(page_title)}</h1>
    <p class="report-byline">{esc(byline)}</p>
  </header>
  {abstract_html}
  {"\n".join(sections_html)}
  {refs_html}
  <footer class="provenance-footer">
    <p>Verified build: {len(resolved.metrics)} bound metrics checked across {len(resolved.artifact_hashes)} SHA-256 JSON artifacts.</p>
    {repo_link}
    {disclosure}
  </footer>
</main>
<script type="module">{READER_SCROLLSPY_JS}</script>
</body>
</html>
"""
