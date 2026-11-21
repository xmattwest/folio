"""Syndication & Discovery Compiler for Folio (Markdown twin, Zenodo DOI metadata, HF Model Card)."""

from __future__ import annotations

import json

from folio.ir import ResolvedManuscript, TableSpec


def _render_md_table(tbl: TableSpec, resolved: ResolvedManuscript) -> str:
    headers = [resolved.interpolate(h).replace("|", "\\|") for h in tbl.headers]
    if not headers:
        return ""
    lines = [
        f"**{resolved.interpolate(tbl.title)}**",
        "",
        f"| {' | '.join(headers)} |",
        f"| {' | '.join('---' for _ in headers)} |",
    ]
    for row in tbl.rows:
        cells = [resolved.interpolate(c).replace("|", "\\|") for c in row]
        lines.append(f"| {' | '.join(cells)} |")
    if tbl.source:
        lines.append("")
        lines.append(f"*Source: {resolved.interpolate(tbl.source)}*")
    return "\n".join(lines)


def render_markdown_twin(resolved: ResolvedManuscript) -> str:
    """Emit a clean, LLM- and RAG-optimized Markdown twin (`index.md`) with verified metrics."""
    meta = resolved.ir.meta
    title = resolved.interpolate(meta.monograph_title or meta.preprint_title or meta.title)
    subtitle = resolved.interpolate(meta.subtitle) if meta.subtitle else ""
    abstract = resolved.interpolate(meta.abstract or meta.lede)
    pub_date = meta.iso_date or meta.date

    fm = ["---", f'title: "{title.replace(chr(34), chr(39))}"']
    if subtitle:
        fm.append(f'subtitle: "{subtitle.replace(chr(34), chr(39))}"')
    if meta.author:
        fm.append(f'author: "{meta.author}"')
    if meta.orcid:
        fm.append(f'orcid: "{meta.orcid}"')
    if pub_date:
        fm.append(f'date: "{pub_date}"')
    if meta.canonical_url:
        fm.append(f'canonical_url: "{meta.canonical_url}"')
    if meta.pdf_url:
        fm.append(f'pdf_url: "{meta.pdf_url}"')
    if meta.doi:
        fm.append(f'doi: "{meta.doi}"')
    if meta.repo_url:
        fm.append(f'code_repository: "{meta.repo_url}"')
    if meta.hf_model_url:
        fm.append(f'huggingface_model: "{meta.hf_model_url}"')
    if meta.hf_dataset_url:
        fm.append(f'huggingface_dataset: "{meta.hf_dataset_url}"')
    if meta.keywords:
        kw_str = ", ".join(meta.keywords).replace('"', "'")
        fm.append(f'keywords: "{kw_str}"')
    fm.append("---")

    out: list[str] = ["\n".join(fm), "", f"# {title}"]
    if subtitle:
        out.extend(["", f"*{subtitle}*"])
    if abstract:
        out.extend(["", f"> **Abstract:** {abstract}"])

    for p in meta.opening_paragraphs:
        out.extend(["", resolved.interpolate(p)])

    for sec in resolved.ir.sections:
        sec_title = resolved.interpolate(sec.monograph_title or sec.preprint_title)
        hashes = "#" * max(2, min(4, sec.level))
        out.extend(["", f"{hashes} {sec_title}"])
        if sec.caveat:
            out.extend(["", f"> **Scope ({sec.tier}):** {resolved.interpolate(sec.caveat)}"])
        for p in sec.paragraphs:
            out.extend(["", resolved.interpolate(p)])
        for q in sec.quotes:
            q_txt = "\n> ".join(resolved.interpolate(q).splitlines())
            out.extend(["", f"> {q_txt}"])
        if sec.bullets:
            out.append("")
            for b in sec.bullets:
                out.append(f"- {resolved.interpolate(b)}")
        for eid in sec.equation_ids:
            eq = resolved.ir.equations[eid]
            out.extend(["", f"```text\n{eq.unicode}\n```"])
        for fid in sec.figure_ids:
            fig = resolved.ir.figures[fid]
            cap = resolved.interpolate(fig.caption or fig.source)
            out.extend(["", f"> **Figure ({resolved.interpolate(fig.title)}):** {cap}"])
        for tid in sec.table_ids:
            tbl = resolved.ir.tables[tid]
            out.extend(["", _render_md_table(tbl, resolved)])
        for p in sec.post_paragraphs:
            out.extend(["", resolved.interpolate(p)])
        if sec.callout:
            out.extend(["", f"> {resolved.interpolate(sec.callout)}"])

    if resolved.ir.citations:
        out.extend(["", "## References", ""])
        for c in resolved.ir.citations:
            venue = f" *{c.venue}*." if c.venue else ""
            link = f" {c.url}" if c.url else ""
            out.append(f"- {c.authors} ({c.year}). {c.title}.{venue}{link}")

    return "\n".join(out).strip() + "\n"


def render_zenodo_json(resolved: ResolvedManuscript) -> str:
    """Emit a turnkey `.zenodo.json` DataCite/OAI-PMH deposit record for OpenAlex & Google Scholar."""
    meta = resolved.ir.meta
    title = resolved.interpolate(meta.preprint_title or meta.title)
    subtitle = resolved.interpolate(meta.subtitle) if meta.subtitle else ""
    full_title = f"{title}: {subtitle}" if subtitle and subtitle.lower() not in title.lower() else title
    description = resolved.interpolate(meta.abstract or meta.lede or title)

    creator: dict[str, str] = {"name": meta.author or "Unknown Author"}
    if meta.affiliation:
        creator["affiliation"] = meta.affiliation
    if meta.orcid:
        orcid_id = meta.orcid.rstrip("/").split("/")[-1]
        creator["orcid"] = orcid_id

    related: list[dict[str, str]] = []
    if meta.canonical_url:
        related.append({
            "identifier": meta.canonical_url,
            "relation": "isIdenticalTo",
            "resource_type": "publication-preprint",
        })
    if meta.repo_url:
        related.append({
            "identifier": meta.repo_url,
            "relation": "isSupplementedBy",
            "resource_type": "software",
        })
    if meta.hf_model_url:
        related.append({
            "identifier": meta.hf_model_url,
            "relation": "isSupplementedBy",
            "resource_type": "other",
        })
    if meta.hf_dataset_url:
        related.append({
            "identifier": meta.hf_dataset_url,
            "relation": "isSupplementedBy",
            "resource_type": "dataset",
        })
    if meta.part1_url:
        related.append({
            "identifier": meta.part1_url,
            "relation": "continues",
            "resource_type": "publication-preprint",
        })

    payload: dict[str, object] = {
        "upload_type": "publication",
        "publication_type": "preprint",
        "title": full_title,
        "creators": [creator],
        "description": description,
        "access_right": "open",
        "license": "cc-by-4.0",
    }
    if meta.iso_date or meta.date:
        payload["publication_date"] = meta.iso_date or meta.date
    if meta.keywords:
        payload["keywords"] = list(meta.keywords)
    if related:
        payload["related_identifiers"] = related

    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_hf_card_md(resolved: ResolvedManuscript) -> str:
    """Emit a Hugging Face Hub README card stub with `base_model:` YAML frontmatter."""
    meta = resolved.ir.meta
    title = resolved.interpolate(meta.title)
    abstract = resolved.interpolate(meta.abstract or meta.lede)

    yaml_lines = ["---", "license: mit"]
    if meta.base_model:
        yaml_lines.append(f"base_model: {meta.base_model}")
    yaml_lines.extend(["language:", "  - en"])
    if meta.keywords:
        yaml_lines.append("tags:")
        for kw in meta.keywords[:10]:
            slug = kw.lower().replace(" ", "-").replace("/", "-")
            yaml_lines.append(f"  - {slug}")
    yaml_lines.append("---")

    body = ["\n".join(yaml_lines), "", f"# {title}", "", abstract]
    links: list[str] = []
    if meta.canonical_url:
        links.append(f"- **Publication:** [{meta.canonical_url}]({meta.canonical_url})")
    if meta.pdf_url:
        links.append(f"- **PDF:** [{meta.pdf_url}]({meta.pdf_url})")
    if meta.repo_url:
        links.append(f"- **Code Repository:** [{meta.repo_url}]({meta.repo_url})")
    if links:
        body.extend(["", "## Links", "", *links])

    if resolved.ir.tables:
        first_tbl = next(iter(resolved.ir.tables.values()))
        body.extend(["", "## Summary Scorecard", "", _render_md_table(first_tbl, resolved)])

    return "\n".join(body).strip() + "\n"
