"""Target 4: X Long-Form Article + Card Kit renderer.

Produces mobile-first structural beats with clean Unicode math/comparisons
(zero raw LaTeX, zero em dashes, zero hashtags/emojis per VOICE.md) paired with
16:9 / 4:3 Dawn State card PNG references.
"""

from __future__ import annotations

import re

from folio.ir import ResolvedManuscript
from folio.tokens import ARROW, MINUS, TIMES

LATEX_SUBS: tuple[tuple[str, str], ...] = (
    (r"\\times\b", TIMES),
    (r"\\rightarrow\b|\\to\b", ARROW),
    (r"\\le\b|\\leq\b", "\u2264"),
    (r"\\ge\b|\\geq\b", "\u2265"),
    (r"\\approx\b", "\u2248"),
    (r"\\neq\b", "\u2260"),
    (r"\\pm\b", "\u00b1"),
    (r"\\perp\b", "\u22a5"),
    (r"\\top\b", "T"),
    (r"\\sigma\b", "\u03c3"),
    (r"\\beta\b", "\u03b2"),
    (r"\\cdot\b", "\u00b7"),
)


def clean_unicode_math(text: str) -> str:
    """Strip inline LaTeX delimiters and normalize common math operators to Unicode."""
    out = text
    for pat, repl in LATEX_SUBS:
        out = re.sub(pat, repl, out)
    # Strip paired $...$ while preserving literal currency like $1,000
    out = re.sub(r"\$([^$\d][^$]*)\$", r"\1", out)
    # Replace remaining ASCII minus before digits inside math expressions
    out = re.sub(r"(?<![A-Za-z0-9/])-(\d)", rf"{MINUS}\1", out)
    return out


def render_x_article(
    resolved: ResolvedManuscript,
    card_png_paths: dict[str, str],
) -> str:
    """Compile a ResolvedManuscript into an X Long-Form Article Markdown + card kit."""
    ir = resolved.ir
    meta = ir.meta
    lines: list[str] = []

    hook = resolved.interpolate(meta.x_hook or meta.lede or meta.subtitle)
    lines.append(clean_unicode_math(hook))
    lines.append("")

    hero_fid = meta.hero_figure
    if hero_fid and hero_fid in ir.figures:
        hfig = ir.figures[hero_fid]
        h_card = card_png_paths.get(hero_fid, f"cards/{hero_fid}_{hfig.card_aspect.replace(':', 'x')}.png")
        h_cap = clean_unicode_math(resolved.interpolate(hfig.caption or hfig.title))
        lines.append(f"[Attach Card: {h_card}]")
        lines.append(h_cap)
        lines.append("")

    for sec in ir.sections:
        if sec.hr_before:
            lines.append("---")
            lines.append("")
        heading = clean_unicode_math(resolved.interpolate(sec.monograph_title))
        prefix = "###" if sec.level >= 3 else "##"
        lines.append(f"{prefix} {heading}")
        lines.append("")

        for p in sec.paragraphs:
            lines.append(clean_unicode_math(resolved.interpolate(p)))
            lines.append("")

        for q in sec.quotes:
            for qpart in resolved.interpolate(q).split("\n\n"):
                qclean = clean_unicode_math(qpart.strip().replace("\n", " "))
                if qclean:
                    lines.append(f"> {qclean}")
            lines.append("")

        for eid in sec.equation_ids:
            eq = ir.equations[eid]
            lines.append(clean_unicode_math(eq.unicode))
            lines.append("")

        for fid in sec.figure_ids:
            if fid == hero_fid:
                continue
            fig = ir.figures[fid]
            card_path = card_png_paths.get(fid, f"cards/{fid}_{fig.card_aspect.replace(':', 'x')}.png")
            caption = clean_unicode_math(resolved.interpolate(fig.caption or fig.title))
            lines.append(f"[Attach Card: {card_path}]")
            lines.append(caption)
            lines.append("")

        for b in sec.bullets:
            lines.append(f"- {clean_unicode_math(resolved.interpolate(b))}")
        if sec.bullets:
            lines.append("")

        for p in sec.post_paragraphs:
            lines.append(clean_unicode_math(resolved.interpolate(p)))
            lines.append("")

        if sec.callout:
            lines.append(f"> {clean_unicode_math(resolved.interpolate(sec.callout))}")
            lines.append("")

    if meta.canonical_url:
        lines.append(f"Interactive web edition & full tables by {meta.author}: {meta.canonical_url}")
    if meta.part1_url:
        lines.append(f"{meta.part1_label}: {meta.part1_url}")
    if meta.repo_url:
        lines.append(f"Code and raw JSON artifacts: {meta.repo_url}")

    return "\n".join(lines).strip() + "\n"
