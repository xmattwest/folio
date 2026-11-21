"""Shared HTML helpers, inline markdown rendering, and shelltoho.me Dawn State editorial CSS."""

from __future__ import annotations

import html
import json
import re

from folio.ir import ResolvedManuscript, SectionSpec, TableSpec

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
INLINE_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*|#[^)\s]+)\)")
INLINE_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
INLINE_ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def slugify_id(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "section"


def render_inline_md(text: str) -> str:
    """Safely convert basic inline Markdown (code, links, bold, italic) to HTML."""
    s = html.escape(text, quote=False)
    s = INLINE_CODE_RE.sub(r"<code>\1</code>", s)

    def _link_repl(m: re.Match[str]) -> str:
        lbl, url = m.group(1), m.group(2)
        if url.startswith(("#", "/")) or "shelltoho.me" in url:
            return f'<a href="{url}">{lbl}</a>'
        return f'<a href="{url}" target="_blank" rel="noopener">{lbl}</a>'

    s = INLINE_LINK_RE.sub(_link_repl, s)
    s = INLINE_BOLD_RE.sub(r"<strong>\1</strong>", s)
    s = INLINE_ITALIC_RE.sub(r"<em>\1</em>", s)
    return s


def render_math_html(unicode_math: str) -> str:
    """Format clean Unicode math expressions into typographic serif HTML (sub/sup/italics)."""
    s = html.escape(unicode_math.strip(), quote=False)
    s = s.replace("^T", "<sup>\u22a4</sup>")
    s = re.sub(r"\^\(([^)]+)\)", r"<sup>(\1)</sup>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-\u2212]+)", r"<sup>\1</sup>", s)
    s = re.sub(r"_([A-Za-z0-9]+)", r"<sub>\1</sub>", s)
    s = re.sub(r"\bl\b", "\u2113", s)
    s = re.sub(r" {2,}", " &emsp; ", s)
    # Italicize standalone single-letter math symbols outside HTML tags
    parts = re.split(r"(<[^>]+>)", s)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\b([A-Za-z])\b", r"<i>\1</i>", parts[i])
    return "".join(parts)


def render_seo_head_html(
    resolved: ResolvedManuscript,
    *,
    page_title: str,
    description: str,
    url: str = "",
    schema_type: str = "ScholarlyArticle",
) -> str:
    """Emit canonical, Google Scholar citation_*, OpenGraph/Twitter, and Schema.org JSON-LD tags."""
    meta = resolved.ir.meta
    tags: list[str] = [
        f'<meta name="description" content="{esc(description)}">',
        f'<meta name="author" content="{esc(meta.author)}">',
    ]
    if meta.keywords:
        tags.append(f'<meta name="keywords" content="{esc(", ".join(meta.keywords))}">')
    if url:
        tags.append(f'<link rel="canonical" href="{esc(url)}">')

    # Highwire Press / Google Scholar / Semantic Scholar metadata
    tags.append(f'<meta name="citation_title" content="{esc(page_title)}">')
    tags.append(f'<meta name="citation_author" content="{esc(meta.author)}">')
    cite_date = (meta.iso_date or meta.date).replace("-", "/")
    if cite_date:
        tags.append(f'<meta name="citation_publication_date" content="{esc(cite_date)}">')
    if url:
        tags.append(f'<meta name="citation_fulltext_html_url" content="{esc(url)}">')

    # Open Graph & Twitter card metadata
    tags.append('<meta property="og:site_name" content="shelltoho.me">')
    tags.append('<meta property="og:type" content="article">')
    tags.append(f'<meta property="og:title" content="{esc(page_title)} | {esc(meta.author)}">')
    tags.append(f'<meta property="og:description" content="{esc(description)}">')
    if url:
        tags.append(f'<meta property="og:url" content="{esc(url)}">')
    if meta.author_url:
        tags.append(f'<meta property="article:author" content="{esc(meta.author_url)}">')
    if meta.iso_date:
        tags.append(f'<meta property="article:published_time" content="{esc(meta.iso_date)}">')
    if meta.og_image:
        tags.append(f'<meta property="og:image" content="{esc(meta.og_image)}">')
    tags.append('<meta name="twitter:card" content="summary_large_image">')
    tags.append(f'<meta name="twitter:title" content="{esc(page_title)} | {esc(meta.author)}">')
    tags.append(f'<meta name="twitter:description" content="{esc(description)}">')
    if meta.og_image:
        tags.append(f'<meta name="twitter:image" content="{esc(meta.og_image)}">')

    # Schema.org JSON-LD entity linking author (@id) <-> ScholarlyArticle <-> GitHub & Part 1
    author_obj: dict[str, object] = {
        "@type": "Person",
        "name": meta.author,
    }
    if meta.author_id:
        author_obj["@id"] = meta.author_id
    if meta.author_url:
        author_obj["url"] = meta.author_url
    if meta.same_as:
        author_obj["sameAs"] = list(meta.same_as)

    ld: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": schema_type,
        "headline": page_title,
        "name": page_title,
        "description": description,
        "author": author_obj,
        "inLanguage": "en",
    }
    if url:
        ld["@id"] = f"{url.rstrip('/')}/#article"
        ld["url"] = url
        ld["mainEntityOfPage"] = url
    if meta.iso_date:
        ld["datePublished"] = meta.iso_date
        ld["dateModified"] = meta.iso_date
    if meta.og_image:
        ld["image"] = meta.og_image
    if meta.keywords:
        ld["keywords"] = list(meta.keywords)
    if meta.part1_url:
        ld["isBasedOn"] = {
            "@type": "ScholarlyArticle",
            "name": meta.part1_label,
            "url": meta.part1_url,
        }
    if meta.repo_url:
        ld["sameAs"] = [meta.repo_url]

    ld_json = json.dumps(ld, ensure_ascii=False).replace("<", "\\u003c")
    tags.append(f'<script type="application/ld+json">{ld_json}</script>')
    return "\n".join(tags)


def render_blockquote_html(raw_quote: str, resolved: ResolvedManuscript) -> str:
    """Render a Dawn State single-line pull-quote or multi-part contrast blockquote."""
    interpolated = resolved.interpolate(raw_quote)
    parts = [p.strip() for p in interpolated.split("\n\n") if p.strip()]
    inner_ps: list[str] = []
    for part in parts:
        lines = [render_inline_md(ln.strip()) for ln in part.split("\n") if ln.strip()]
        inner_ps.append(f"<p>{'<br>'.join(lines)}</p>")
    return f"<blockquote>{''.join(inner_ps)}</blockquote>"


def render_table_html(tbl: TableSpec, resolved: ResolvedManuscript, table_number: int | None = None) -> str:
    """Render a Dawn State verified data table."""
    title = resolved.interpolate(tbl.title)
    subtitle = resolved.interpolate(tbl.subtitle) if tbl.subtitle else ""
    source = resolved.interpolate(tbl.source) if tbl.source else ""
    caveat = resolved.interpolate(tbl.caveat) if tbl.caveat else ""

    prefix = f"Table {table_number}. " if table_number is not None else ""
    tier_badge = ""
    if tbl.tier in ("exploratory", "negative") and table_number is not None:
        tier_badge = f'<span class="tier-tag tier-{esc(tbl.tier)}">{esc(tbl.tier.upper())}</span> '

    right_cols = set(tbl.right_align_cols)
    ths = "".join(
        f'<th scope="col"{" class=\"num\"" if i in right_cols else ""}>{render_inline_md(resolved.interpolate(h))}</th>'
        for i, h in enumerate(tbl.headers)
    )
    body_rows: list[str] = []
    for r_idx, row in enumerate(tbl.rows):
        row_cls = ' class="row-highlight"' if tbl.highlight_row is not None and r_idx == tbl.highlight_row else ""
        tds = "".join(
            f'<td{" class=\"num\"" if c_idx in right_cols else ""}>{render_inline_md(resolved.interpolate(cell))}</td>'
            for c_idx, cell in enumerate(row)
        )
        body_rows.append(f"<tr{row_cls}>{tds}</tr>")

    sub_txt = f" — {esc(subtitle)}" if subtitle else ""
    notes: list[str] = []
    if caveat:
        notes.append(f"<strong>Scope:</strong> {esc(caveat)}")
    if source:
        notes.append(esc(source))
    note_html = f'<p class="table-note">{" ".join(notes)}</p>' if notes else ""

    return (
        f'<div class="folio-table-block" id="tbl-{esc(tbl.id)}">'
        f'<div class="table-scroll" tabindex="0" role="region" aria-label="{esc(title)}">'
        f"<table>"
        f"<caption>{tier_badge}<strong>{esc(prefix + title)}</strong>{sub_txt.replace(' — ', ' · ')}</caption>"
        f"<thead><tr>{ths}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        f"</table></div>"
        f"{note_html}"
        f"</div>"
    )


def build_sidebar_toc_html(
    sections: tuple[SectionSpec, ...],
    resolved: ResolvedManuscript,
    *,
    use_preprint_titles: bool = False,
    numbered_map: dict[str, str] | None = None,
    has_abstract: bool = False,
    has_references: bool = False,
) -> str:
    """Build nested shelltoho.me <details class='reader-subsections'> sidebar TOC."""
    groups: list[tuple[str, str, list[tuple[int, str, str]]]] = []
    if has_abstract:
        groups.append(("abstract", "Abstract", []))

    for sec in sections:
        raw_t = sec.preprint_title if use_preprint_titles else sec.monograph_title
        label = resolved.interpolate(raw_t)
        if numbered_map and sec.id in numbered_map:
            label = f"{numbered_map[sec.id]} {label}"
        sec_anchor = f"sec-{sec.id}"
        if sec.level <= 2 or not groups:
            groups.append((sec_anchor, label, []))
        else:
            groups[-1][2].append((sec.level, sec_anchor, label))

    if has_references:
        groups.append(("references", "References", []))

    items: list[str] = []
    for anchor_id, label, children in groups:
        top_link = f'<a href="#{esc(anchor_id)}" data-reader-section>{esc(label)}</a>'
        if children:
            sub_lis = "".join(
                f'<li class="reader-level-{lvl}"><a href="#{esc(cid)}" data-reader-section>{esc(clbl)}</a></li>'
                for lvl, cid, clbl in children
            )
            items.append(
                f"<li>{top_link}<details class=\"reader-subsections\"><summary>Subsections</summary>"
                f"<ul>{sub_lis}</ul></details></li>"
            )
        else:
            items.append(f"<li>{top_link}</li>")
    return "".join(items)


READER_SCROLLSPY_JS = """// Native anchor navigation enhancement matching shelltoho.me/pubs/
const sidebar = document.querySelector('.reader-sidebar');
const contents = document.querySelector('.reader-contents');
const links = Array.from(document.querySelectorAll('[data-reader-section]'));
const headings = links.map((link) => document.getElementById(decodeURIComponent(link.hash.slice(1))));
const mobile = window.matchMedia('(max-width: 760px)');
const setLayout = () => { if (contents) contents.open = !mobile.matches; };
setLayout();
mobile.addEventListener('change', setLayout);

let current = null;
const markCurrent = (heading) => {
  if (!heading || heading === current) return;
  current = heading;
  links.forEach((link) => {
    if (decodeURIComponent(link.hash.slice(1)) === heading.id) {
      link.setAttribute('aria-current', 'location');
      const group = link.closest('.reader-subsections');
      if (group) group.open = true;
    } else link.removeAttribute('aria-current');
  });
};

let scheduled = false;
const update = () => {
  scheduled = false;
  const threshold = mobile.matches && sidebar ? sidebar.getBoundingClientRect().bottom + 30 : 80;
  let active = headings.find(Boolean) || null;
  for (const heading of headings) {
    if (!heading) continue;
    if (heading.getBoundingClientRect().top <= threshold) active = heading;
    else break;
  }
  markCurrent(active);
};
window.addEventListener('scroll', () => {
  if (!scheduled) { scheduled = true; requestAnimationFrame(update); }
}, { passive: true });
window.addEventListener('resize', update);
window.addEventListener('hashchange', update);
sidebar?.addEventListener('click', (event) => {
  const link = event.target.closest('a[href^="#"]');
  if (link && mobile.matches && contents) contents.open = false;
});
update();"""


# Exact Dawn State editorial web context tokens & shelltoho.me/pubs/ stylesheet
SHELLTOHO_EDITORIAL_CSS = """
:root {
  --wp-canvas: #F7F6EF;
  --wp-surface: #FDFCF8;
  --wp-well: #F7F6EF;
  --wp-text-primary: #0F0F0F;
  --wp-text-secondary: #1E3447;
  --wp-structure: #2C3E50;
  --wp-link: #405943;
  --wp-focus: #405943;
  --wp-kicker: #1E3447;
  --wp-emphasis: #F39C12;
  --wp-emphasis-text: #96590A;
  --wp-outcome-positive: #87A96B;
  --wp-outcome-positive-text: #5F7F4A;
  --wp-context: #808B90;
  --wp-on-structure: #FFFFF0;
  --wp-ui-active: #405943;
  --wp-on-ui-active: #FDFCF8;
  --wp-ui-border: #DCE0D3;
  --wp-personal-text: #303C32;
  --wp-personal-muted: #687063;
  --wp-font-publication: "Newsreader", Georgia, serif;
  --wp-weight-publication: 600;
  --wp-tracking-publication: -0.04em;
  --wp-font-heading: "Inter", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
  --wp-font-body: "Inter", -apple-system, BlinkMacSystemFont, Arial, sans-serif;
  --wp-font-code: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  --wp-publication-size: 2rem;
  --wp-publication-line-height: 1.25;
  --wp-radius-small: 8px;
  --wp-radius-container: 12px;
}
*, *::before, *::after { box-sizing: border-box; }
html { background: var(--wp-canvas); color: var(--wp-text-primary); color-scheme: light; }
body ::selection { background: var(--wp-ui-active); color: var(--wp-on-ui-active); }
.reader-skip { position: fixed; top: -100px; left: 15px; padding: 12px 18px; background: var(--wp-surface); color: var(--wp-link); z-index: 50; font: 14px var(--wp-font-body); }
.reader-skip:focus { top: 15px; }
body .reader-title,
body .reader-page h1 {
  font-family: var(--wp-font-publication);
  font-weight: var(--wp-weight-publication);
  font-size: var(--wp-publication-size);
  line-height: var(--wp-publication-line-height);
  letter-spacing: var(--wp-tracking-publication);
  font-optical-sizing: auto;
  font-style: normal;
}

/* Shared fixed sidebar navigation (shelltoho.me/pubs/) */
.reader-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  width: 248px;
  overflow-y: auto;
  padding: 28px 24px 40px;
  border-right: 1px solid rgba(44, 62, 80, 0.22);
  background: var(--wp-canvas);
  color: var(--wp-text-primary);
  font: 0.875rem/1.5 var(--wp-font-body);
}
.reader-sidebar a { text-decoration: none; }
.reader-home { display: inline-flex; align-items: center; min-height: 44px; color: var(--wp-link); font-size: 0.875rem; margin-bottom: 16px; }
.reader-home:hover { text-decoration: underline; }
.reader-title { display: block; color: var(--wp-text-primary); }
.reader-subtitle { font-size: 0.875rem; line-height: 1.55; color: var(--wp-text-secondary); margin: 10px 0 22px; }
.reader-status { font-size: 0.75rem; line-height: 1.5; color: var(--wp-text-secondary); margin: -12px 0 22px; }
.reader-contents > summary {
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 44px;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--wp-text-secondary);
  cursor: pointer;
  list-style: none;
  border-top: 1px solid rgba(44, 62, 80, 0.22);
}
.reader-contents > summary::-webkit-details-marker { display: none; }
.reader-contents[open] > summary > span { transform: rotate(180deg); }
.reader-sidebar ul { list-style: none; margin: 0; padding: 0; }
.reader-sidebar li { margin: 0; }
.reader-sidebar nav a {
  display: block;
  min-height: 40px;
  padding: 8px 10px;
  border-left: 2px solid transparent;
  color: var(--wp-text-secondary);
  overflow-wrap: anywhere;
  border-radius: var(--wp-radius-small);
}
.reader-sidebar nav a:hover { background: var(--wp-surface); color: var(--wp-link); }
.reader-sidebar nav a[aria-current='location'] {
  border-left-color: var(--wp-ui-active);
  color: var(--wp-on-ui-active);
  background: var(--wp-ui-active);
}
.reader-subsections { padding: 0 0 6px 12px; }
.reader-subsections summary { color: var(--wp-personal-muted); font-size: 11px; padding: 5px 0 7px; cursor: pointer; }
.reader-subsections a { font-size: 12.5px; }

/* Essay / Visual Monograph layout (body.lfm3-report.money-is-moral) */
body.lfm3-report {
  margin: 0;
  padding-left: 248px;
  background: var(--wp-canvas);
  color: var(--wp-text-primary);
  font: 400 1.125rem/1.65 var(--wp-font-body);
  -webkit-font-smoothing: antialiased;
}
.lfm3-report .reader-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 72px 64px 96px;
  border: 0;
  background: var(--wp-canvas);
  font: inherit;
}
.lfm3-report p { margin: 0 0 1.25em; }
.lfm3-report .reader-page a { color: var(--wp-link); text-decoration: underline; text-underline-offset: 0.18em; text-decoration-thickness: 1px; }
.lfm3-report .reader-page a:hover { text-decoration-thickness: 2px; }
.lfm3-report :focus-visible { outline: 2px solid var(--wp-focus); outline-offset: 4px; }
.lfm3-report h1 { margin: 0 0 18px; text-wrap: balance; }
.lfm3-report h1 span { color: var(--wp-text-secondary); }
.lfm3-report h2 { font: 600 1.5rem/1.3 var(--wp-font-heading); letter-spacing: -0.02em; margin-top: 64px; margin-bottom: 22px; scroll-margin-top: 28px; }
.lfm3-report h3 { font: 600 1.125rem/1.4 var(--wp-font-heading); margin-top: 38px; margin-bottom: 14px; scroll-margin-top: 28px; }
.lfm3-report .report-byline { font-size: 0.875rem; color: var(--wp-text-secondary); margin-bottom: 32px; }
.lfm3-report .report-lede { font-size: 1.2rem; line-height: 1.6; color: var(--wp-text-secondary); margin-bottom: 28px; }
.lfm3-report .opening-summary {
  margin: 36px 0 40px;
  padding: 22px 0;
  border-top: 2px solid var(--wp-structure);
  border-bottom: 1px solid rgba(44, 62, 80, 0.22);
  font-size: 1rem;
  line-height: 1.6;
}
.lfm3-report .opening-summary ul { margin: 0; padding-left: 20px; }
.lfm3-report .opening-summary li { margin-bottom: 10px; }
.lfm3-report .opening-summary li:last-child { margin-bottom: 0; }
.lfm3-report figure {
  margin: 40px 0;
  padding: 24px 0 20px;
  border-top: 1px solid rgba(44, 62, 80, 0.22);
  border-bottom: 1px solid rgba(44, 62, 80, 0.22);
}
.lfm3-report .figure-title { font-size: 1.25rem; font-weight: 600; line-height: 1.38; letter-spacing: -0.02em; margin: 0 0 6px; }
.lfm3-report .figure-subtitle { font-size: 1rem; line-height: 1.5; color: var(--wp-text-secondary); margin: 0 0 22px; }
.lfm3-report .figure-scroll { overflow-x: auto; overflow-y: hidden; margin: 0 0 14px; scrollbar-width: thin; }
.lfm3-report .figure-scroll svg { display: block; width: 100%; min-width: 600px; height: auto; }
.lfm3-report figcaption { font-size: 0.875rem; line-height: 1.6; color: var(--wp-text-secondary); margin-top: 16px; }
.lfm3-report .figure-data { font-size: 0.875rem; margin-top: 8px; }
.lfm3-report .figure-data > summary { padding: 8px 0; cursor: pointer; font-weight: 400; color: var(--wp-text-secondary); }
.lfm3-report .figure-alt-prose { margin: 6px 0 12px; color: var(--wp-text-secondary); }
.lfm3-report figure.media-figure,
body.preprint-sheet figure.media-figure {
  border: 0;
  padding: 6px 0 0;
}
figure.media-figure img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: var(--wp-radius-small);
  border: 1px solid var(--wp-ui-border);
}

/* Money-is-moral blockquote, code, list, and hr rules */
.lfm3-report blockquote {
  margin: 32px 0;
  padding: 22px 24px;
  background: var(--wp-surface);
  border: 1px solid var(--wp-ui-border);
  border-radius: var(--wp-radius-container);
  font-size: 1rem;
  line-height: 1.65;
}
.lfm3-report blockquote:not(:has(p + p)) {
  padding: 20px 0;
  background: transparent;
  border: 0;
  border-top: 1px solid rgba(44, 62, 80, 0.22);
  border-bottom: 1px solid rgba(44, 62, 80, 0.22);
  border-radius: 0;
  font-size: 1.125rem;
  line-height: 1.6;
  color: var(--wp-text-secondary);
}
.lfm3-report blockquote p { margin: 0; }
.lfm3-report blockquote p + p {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--wp-ui-border);
}
.lfm3-report blockquote strong {
  display: inline-block;
  margin-bottom: 4px;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--wp-text-secondary);
}
.lfm3-report blockquote em { font-style: normal; color: var(--wp-text-primary); }
.lfm3-report ul, .lfm3-report ol { margin: 0 0 1.25em; padding-left: 24px; }
.lfm3-report li { margin-bottom: 12px; }
.lfm3-report li:last-child { margin-bottom: 0; }
.lfm3-report code {
  font-family: var(--wp-font-code);
  background: var(--wp-surface);
  border: 1px solid var(--wp-ui-border);
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 0.875em;
}
.lfm3-report hr {
  border: 0;
  border-top: 2px solid var(--wp-structure);
  margin: 56px 0 0;
}
.lfm3-report .example-strip {
  margin: 28px 0;
  padding: 4px 0 4px 20px;
  border-left: 2px solid var(--wp-structure);
  font-size: 1rem;
  color: var(--wp-text-secondary);
}

/* Preprint 8.5in sheet layout (multiply-by-a-million style) */
body.preprint-sheet {
  margin: 0;
  padding-left: 270px;
  background: var(--wp-canvas);
  color: var(--wp-text-primary);
  font: 400 1rem/1.65 var(--wp-font-body);
  -webkit-font-smoothing: antialiased;
}
body.preprint-sheet .reader-sidebar { width: 270px; }
body.preprint-sheet .reader-status { text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px; color: var(--wp-link); }
body.preprint-sheet .reader-page {
  max-width: 8.5in;
  margin: 24px auto;
  padding: 0.9in 0.875in;
  background: var(--wp-surface);
  border: 1px solid var(--wp-ui-border);
  border-radius: var(--wp-radius-container);
}
body.preprint-sheet .report-header { margin-bottom: 28px; }
body.preprint-sheet .report-byline { font-size: 0.9rem; color: var(--wp-text-secondary); margin: 8px 0 0; }
body.preprint-sheet .abstract-box {
  margin: 24px 0 32px;
  padding: 18px 22px;
  background: var(--wp-canvas);
  border-radius: var(--wp-radius-small);
  font-size: 0.94rem;
  line-height: 1.6;
}
body.preprint-sheet .abstract-box h2 {
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--wp-text-secondary);
  margin: 0 0 8px;
}
body.preprint-sheet h2 { font: 600 1.3rem/1.3 var(--wp-font-heading); letter-spacing: -0.015em; margin: 40px 0 14px; scroll-margin-top: 28px; }
body.preprint-sheet h3 { font: 600 1.06rem/1.35 var(--wp-font-heading); margin: 28px 0 10px; scroll-margin-top: 28px; }
body.preprint-sheet p { margin: 0 0 1em; }
body.preprint-sheet .reader-page a { color: var(--wp-link); text-decoration: underline; text-underline-offset: 0.18em; }
body.preprint-sheet code { font-family: var(--wp-font-code); font-size: 0.86em; background: var(--wp-canvas); padding: 1px 4px; border-radius: 3px; }
body.preprint-sheet figure { margin: 30px 0; padding: 18px 0; border-top: 1px solid rgba(44, 62, 80, 0.22); border-bottom: 1px solid rgba(44, 62, 80, 0.22); }
body.preprint-sheet .figure-title { font-size: 1.05rem; font-weight: 600; margin: 0 0 4px; }
body.preprint-sheet .figure-subtitle { font-size: 0.9rem; color: var(--wp-text-secondary); margin: 0 0 16px; }
body.preprint-sheet .figure-scroll { overflow-x: auto; }
body.preprint-sheet figcaption { font-size: 0.85rem; color: var(--wp-text-secondary); margin-top: 12px; line-height: 1.5; }
body.preprint-sheet .figure-data { font-size: 0.85rem; margin-top: 8px; }
body.preprint-sheet .figure-data > summary { cursor: pointer; color: var(--wp-text-secondary); }
body.preprint-sheet blockquote { margin: 20px 0; padding: 12px 18px; border-left: 2px solid var(--wp-structure); color: var(--wp-text-secondary); font-size: 0.95rem; }
body.preprint-sheet blockquote p { margin: 0; }
body.preprint-sheet blockquote p + p { margin-top: 10px; }

/* Shared tables, equations, caveats, citations */
.folio-table-block { margin: 32px 0; }
.table-scroll { overflow-x: auto; margin-bottom: 8px; }
table { border-collapse: collapse; width: 100%; font-size: 0.875rem; font-variant-numeric: tabular-nums; }
table caption { caption-side: top; text-align: left; color: var(--wp-text-primary); padding-bottom: 10px; font-size: 0.94rem; line-height: 1.45; }
th, td { text-align: left; padding: 9px 12px 9px 0; border-bottom: 1px solid rgba(44, 62, 80, 0.22); vertical-align: top; }
thead th { border-top: 1.5px solid var(--wp-structure); border-bottom: 2px solid var(--wp-structure); font-weight: 600; color: var(--wp-text-secondary); white-space: nowrap; }
tbody tr:last-child td, tbody tr:last-child th { border-bottom: 1.5px solid var(--wp-structure); }
th.num, td.num { text-align: right; padding-right: 0; padding-left: 12px; white-space: nowrap; }
tr.row-highlight td, tr.row-highlight th { font-weight: 600; }
.table-note { font-size: 0.82rem; color: var(--wp-text-secondary); margin: 6px 0 0; line-height: 1.5; }
.table-drawer {
  font-size: 1rem;
  border-bottom: 1px solid rgba(44, 62, 80, 0.22);
  margin: 20px 0 28px;
}
.table-drawer > summary {
  padding: 12px 0;
  min-height: 44px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--wp-text-secondary);
}
.table-drawer[open] > summary { margin-bottom: 10px; }
.table-drawer .folio-table-block { margin: 0 0 16px; }
.equation-block {
  margin: 24px 0;
  padding: 14px 20px;
  background: var(--wp-surface);
  border: 1px solid var(--wp-ui-border);
  border-radius: var(--wp-radius-small);
  font-family: var(--wp-font-publication);
  font-size: 1.08rem;
  letter-spacing: 0.01em;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  overflow-x: auto;
}
body.preprint-sheet .equation-block { background: var(--wp-canvas); }
.equation-label { color: var(--wp-context); font-size: 0.82rem; white-space: nowrap; }
.section-caveat {
  font-size: 0.92rem;
  color: var(--wp-text-secondary);
  padding: 10px 0 10px 16px;
  border-left: 2px solid var(--wp-emphasis);
  margin: 0 0 20px;
}
.tier-tag {
  display: inline-block;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 1px 6px;
  border-radius: 4px;
  vertical-align: 2px;
  margin-right: 6px;
}
.tier-exploratory { background: #F5EEDC; color: var(--wp-emphasis-text); border: 1px solid var(--wp-emphasis-text); }
.tier-negative { background: #F5EEDC; color: var(--wp-structure); border: 1px solid var(--wp-structure); }
.citations-list { font-size: 0.9rem; padding-left: 20px; line-height: 1.55; }
.citations-list li { margin-bottom: 8px; }
.provenance-footer {
  margin-top: 48px;
  padding-top: 18px;
  border-top: 1px solid rgba(44, 62, 80, 0.22);
  font-size: 0.85rem;
  color: var(--wp-text-secondary);
}

@media (max-width: 1100px) and (min-width: 761px) {
  .lfm3-report .reader-page { padding: 48px 32px 72px; }
  body.preprint-sheet .reader-page { margin: 18px 20px; padding: 44px 34px; }
}
@media (max-width: 760px) {
  body.lfm3-report, body.preprint-sheet { padding-left: 0; }
  .reader-sidebar, body.preprint-sheet .reader-sidebar {
    position: sticky;
    inset: auto;
    top: 0;
    width: auto;
    padding: 8px 24px 0;
    border-right: 0;
    border-bottom: 1px solid var(--wp-ui-border);
    z-index: 10;
  }
  .reader-home { min-height: 36px; margin: 0 18px 0 0; font-size: 12px; }
  .reader-title { display: inline; font-size: 1rem; }
  .reader-subtitle, .reader-status { display: none; }
  .reader-contents > summary { min-height: 36px; border-top: 0; }
  .reader-contents nav { max-height: 45svh; overflow-y: auto; padding-bottom: 12px; }
  .lfm3-report .reader-page, body.preprint-sheet .reader-page { border: 0; border-radius: 0; padding: 36px 24px 64px; margin: 0; }
}
@media print {
  body.lfm3-report, body.preprint-sheet { padding: 0; background: #fff; }
  .reader-sidebar, .reader-skip { display: none; }
  .lfm3-report .reader-page, body.preprint-sheet .reader-page { border: 0; margin: 0; padding: 0; max-width: none; }
}
"""
