"""Canonical Claim & Evidence IR for Folio.

Loads a project-agnostic research manifest (TOML or JSON), resolves every
quantitative metric via RFC 6901 JSON Pointer against upstream JSON artifacts
(with optional SHA-256 verification and deterministic derived expressions),
and provides verified metric interpolation for all publication surfaces.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from folio.tokens import FormatSpec, fmt_number

VALID_TIERS = frozenset({"primary", "exploratory", "negative"})
METRIC_TOKEN_RE = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


class IRError(ValueError):
    """Raised when a manifest or JSON Pointer binding is invalid."""


@dataclass(frozen=True)
class ArtifactSpec:
    alias: str
    path: str
    sha256: str | None = None
    description: str = ""


@dataclass(frozen=True)
class MetricSpec:
    id: str
    tier: str  # primary | exploratory | negative
    pointer: str | None = None  # e.g. "phase8#/part_a/hourglass_10pct/kl"
    derive: str | None = None  # pct_change | ratio | diff | sum | scale
    inputs: tuple[str, ...] = ()
    factor: float = 1.0
    fmt: FormatSpec = field(default_factory=FormatSpec)
    scope: str = ""
    caveat: str = ""
    expected: float | int | None = None
    tolerance: float = 1e-6


@dataclass(frozen=True)
class ResolvedMetric:
    spec: MetricSpec
    raw_value: float
    formatted: str
    source_pointers: tuple[str, ...]


@dataclass(frozen=True)
class TableSpec:
    id: str
    title: str
    subtitle: str = ""
    source: str = ""
    tier: str = "primary"
    caveat: str = ""
    headers: tuple[str, ...] = ()
    rows: tuple[tuple[str, ...], ...] = ()
    highlight_row: int | None = None
    right_align_cols: tuple[int, ...] = ()


@dataclass(frozen=True)
class FigureSeries:
    label: str
    values: tuple[str | float, ...]  # metric IDs ("{{id}}") or resolved pointers
    role: str = "primary"  # primary | focus | secondary | context
    x_values: tuple[str | float, ...] = ()  # optional X coordinates for scatter plots
    point_labels: tuple[str, ...] = ()  # optional per-point labels for scatter plots


@dataclass(frozen=True)
class FigureSpec:
    id: str
    kind: str  # bar | grouped_bar | line | slope | scatter | schematic
    title: str
    subtitle: str
    source: str
    alt: str
    kicker: str = ""
    accent: str = ""  # substring of title highlighted in Copper Deep on cards
    caption: str = ""  # optional extended <figcaption> prose (defaults to source)
    tier: str = "primary"
    caveat: str = ""
    note: str = ""
    categories: tuple[str, ...] = ()
    series: tuple[FigureSeries, ...] = ()
    x_label: str = ""
    x_unit: str = ""
    x_decimals: int = 1
    x_min: float | None = None
    x_max: float | None = None
    x_reference_value: float | None = None
    x_reference_label: str = ""
    y_label: str = ""
    y_unit: str = ""
    y_decimals: int = 2
    y_min: float | None = None
    y_max: float | None = None
    focus_index: int | None = None
    reference_value: float | None = None
    reference_label: str = ""
    # For schematic / architecture diagrams
    nodes: tuple[dict[str, Any], ...] = ()
    edges: tuple[dict[str, Any], ...] = ()
    # For external verified media (e.g., animated GIF / MP4 / bespoke PNG)
    media_path: str = ""
    media_sha256: str = ""
    # For X card aspect ratio
    card_aspect: str = "16:9"  # 16:9 | 4:3


@dataclass(frozen=True)
class EquationSpec:
    id: str
    latex: str
    unicode: str
    label: str = ""


@dataclass(frozen=True)
class SectionSpec:
    id: str
    preprint_title: str
    monograph_title: str
    level: int = 2
    tier: str = "primary"
    caveat: str = ""
    hr_before: bool = False
    paragraphs: tuple[str, ...] = ()
    quotes: tuple[str, ...] = ()
    bullets: tuple[str, ...] = ()
    post_paragraphs: tuple[str, ...] = ()
    callout: str = ""
    figure_ids: tuple[str, ...] = ()
    table_ids: tuple[str, ...] = ()
    equation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CitationSpec:
    key: str
    authors: str
    year: str
    title: str
    venue: str = ""
    url: str = ""


@dataclass(frozen=True)
class DocumentMeta:
    title: str
    subtitle: str
    author: str
    date: str
    affiliation: str = "Independent research"
    wordmark: str = ""
    home_label: str = "\u2190 Matt West"
    home_url: str = "/"
    monograph_status: str = "Essay"
    preprint_status: str = "Preprint \u00b7 Not peer reviewed"
    preprint_title: str = ""
    monograph_title: str = ""
    substack_title_alt: str = ""
    abstract: str = ""
    lede: str = ""
    opening_paragraphs: tuple[str, ...] = ()
    opening_summary: tuple[str, ...] = ()
    hero_figure: str = ""
    x_hook: str = ""
    ai_disclosure: str = ""
    repo_url: str = ""
    canonical_url: str = ""
    preprint_url: str = ""
    author_url: str = "https://shelltoho.me/"
    author_id: str = "https://shelltoho.me/#matt"
    iso_date: str = ""
    og_image: str = ""
    same_as: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    part1_url: str = ""
    part1_label: str = "Part 1"
    substack_tables: bool = False
    allow_numbers: tuple[str, ...] = ()
    orcid: str = ""
    doi: str = ""
    pdf_url: str = ""
    markdown_url: str = ""
    seo_title: str = ""
    hf_model_url: str = ""
    hf_dataset_url: str = ""
    base_model: str = ""


@dataclass(frozen=True)
class ManuscriptIR:
    manifest_path: Path
    base_dir: Path
    meta: DocumentMeta
    artifacts: dict[str, ArtifactSpec]
    metrics: dict[str, MetricSpec]
    sections: tuple[SectionSpec, ...]
    tables: dict[str, TableSpec]
    figures: dict[str, FigureSpec]
    equations: dict[str, EquationSpec]
    citations: tuple[CitationSpec, ...]


@dataclass(frozen=True)
class ResolvedManuscript:
    ir: ManuscriptIR
    artifact_hashes: dict[str, str]
    metrics: dict[str, ResolvedMetric]

    def interpolate(self, text: str) -> str:
        """Replace {{metric_id}} tokens with verified formatted values."""
        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in self.metrics:
                raise IRError(f"Unknown metric reference '{{{{{key}}}}}'")
            return self.metrics[key].formatted

        return METRIC_TOKEN_RE.sub(_replace, text)

    def metric_value(self, ref: str | float | int) -> float:
        """Resolve a display-scaled numeric value from a float, metric token, or metric ID."""
        if isinstance(ref, (int, float)):
            return float(ref)
        m = METRIC_TOKEN_RE.fullmatch(ref.strip())
        key = m.group(1) if m else ref.strip()
        if key in self.metrics:
            rm = self.metrics[key]
            scale = rm.spec.fmt.scale if rm.spec.derive != "scale" else 1.0
            return rm.raw_value * scale
        raise IRError(f"Cannot resolve figure numeric reference '{ref}'")


def resolve_json_pointer(doc: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON Pointer (e.g. '/a/b/0/c') against a JSON document."""
    if pointer in ("", "/"):
        return doc
    if not pointer.startswith("/"):
        raise IRError(f"JSON Pointer must start with '/': '{pointer}'")

    cur = doc
    for raw_token in pointer.lstrip("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if token not in cur:
                raise IRError(f"JSON Pointer key '{token}' not found in '{pointer}'")
            cur = cur[token]
        elif isinstance(cur, list):
            try:
                idx = int(token)
            except ValueError as exc:
                raise IRError(f"JSON Pointer list index '{token}' invalid in '{pointer}'") from exc
            if idx < 0 or idx >= len(cur):
                raise IRError(f"JSON Pointer index {idx} out of range in '{pointer}'")
            cur = cur[idx]
        else:
            raise IRError(f"Cannot traverse into {type(cur).__name__} at '{token}' in '{pointer}'")
    return cur


def _parse_format_spec(raw: dict[str, Any] | None) -> FormatSpec:
    if not raw:
        return FormatSpec()
    return FormatSpec(
        style=str(raw.get("style", "number")),
        decimals=int(raw.get("decimals", 2)),
        signed=bool(raw.get("signed", False)),
        unit=str(raw.get("unit", "")),
        scale=float(raw.get("scale", 1.0)),
        prefix=str(raw.get("prefix", "")),
        suffix=str(raw.get("suffix", "")),
    )


def load_manifest(manifest_path: Path) -> ManuscriptIR:
    """Load a Folio manuscript manifest from TOML or JSON."""
    path = manifest_path.resolve()
    if not path.is_file():
        raise IRError(f"Manifest file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".toml":
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    elif suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise IRError(f"Unsupported manifest extension '{suffix}' (use .toml or .json)")

    base_dir_raw = raw.get("base_dir", ".")
    base_dir = (path.parent / base_dir_raw).resolve()

    meta_raw = raw.get("meta", {})
    author_str = str(meta_raw.get("author", ""))
    default_home = f"\u2190 {author_str}" if author_str else "\u2190 Home"
    meta = DocumentMeta(
        title=str(meta_raw.get("title", "")),
        subtitle=str(meta_raw.get("subtitle", "")),
        author=author_str,
        date=str(meta_raw.get("date", "")),
        affiliation=str(meta_raw.get("affiliation", "Independent research")),
        wordmark=str(meta_raw.get("wordmark", "")),
        home_label=str(meta_raw.get("home_label", default_home)),
        home_url=str(meta_raw.get("home_url", "/")),
        monograph_status=str(meta_raw.get("monograph_status", "Essay")),
        preprint_status=str(meta_raw.get("preprint_status", "Preprint \u00b7 Not peer reviewed")),
        preprint_title=str(meta_raw.get("preprint_title", "")),
        monograph_title=str(meta_raw.get("monograph_title", "")),
        substack_title_alt=str(meta_raw.get("substack_title_alt", "")),
        abstract=str(meta_raw.get("abstract", "")),
        lede=str(meta_raw.get("lede", "")),
        opening_paragraphs=tuple(str(x) for x in meta_raw.get("opening_paragraphs", [])),
        opening_summary=tuple(str(x) for x in meta_raw.get("opening_summary", [])),
        hero_figure=str(meta_raw.get("hero_figure", "")),
        x_hook=str(meta_raw.get("x_hook", "")),
        ai_disclosure=str(meta_raw.get("ai_disclosure", "")),
        repo_url=str(meta_raw.get("repo_url", "")),
        canonical_url=str(meta_raw.get("canonical_url", "")),
        preprint_url=str(meta_raw.get("preprint_url", "")),
        author_url=str(meta_raw.get("author_url", "https://shelltoho.me/")),
        author_id=str(meta_raw.get("author_id", "https://shelltoho.me/#matt")),
        iso_date=str(meta_raw.get("iso_date", "")),
        og_image=str(meta_raw.get("og_image", "")),
        same_as=tuple(str(x) for x in meta_raw.get("same_as", [])),
        keywords=tuple(str(x) for x in meta_raw.get("keywords", [])),
        part1_url=str(meta_raw.get("part1_url", "")),
        part1_label=str(meta_raw.get("part1_label", "Part 1")),
        substack_tables=bool(meta_raw.get("substack_tables", False)),
        allow_numbers=tuple(str(x) for x in meta_raw.get("allow_numbers", [])),
        orcid=str(meta_raw.get("orcid", "")),
        doi=str(meta_raw.get("doi", "")),
        pdf_url=str(meta_raw.get("pdf_url", "")),
        markdown_url=str(meta_raw.get("markdown_url", "")),
        seo_title=str(meta_raw.get("seo_title", "")),
        hf_model_url=str(meta_raw.get("hf_model_url", "")),
        hf_dataset_url=str(meta_raw.get("hf_dataset_url", "")),
        base_model=str(meta_raw.get("base_model", "")),
    )

    artifacts: dict[str, ArtifactSpec] = {}
    for alias, a_raw in raw.get("artifacts", {}).items():
        if isinstance(a_raw, str):
            artifacts[alias] = ArtifactSpec(alias=alias, path=a_raw)
        else:
            artifacts[alias] = ArtifactSpec(
                alias=alias,
                path=str(a_raw["path"]),
                sha256=a_raw.get("sha256"),
                description=str(a_raw.get("description", "")),
            )

    metrics: dict[str, MetricSpec] = {}
    for mid, m_raw in raw.get("metrics", {}).items():
        tier = str(m_raw.get("tier", ""))
        if tier not in VALID_TIERS:
            raise IRError(f"Metric '{mid}' has invalid or missing tier '{tier}' (must be one of {sorted(VALID_TIERS)})")
        fmt_raw = m_raw.get("format") or {
            k: m_raw[k]
            for k in ("style", "decimals", "signed", "unit", "scale", "prefix", "suffix")
            if k in m_raw
        }
        metrics[mid] = MetricSpec(
            id=mid,
            tier=tier,
            pointer=m_raw.get("pointer"),
            derive=m_raw.get("derive"),
            inputs=tuple(str(x) for x in m_raw.get("inputs", [])),
            factor=float(m_raw.get("factor", 1.0)),
            fmt=_parse_format_spec(fmt_raw),
            scope=str(m_raw.get("scope", "")),
            caveat=str(m_raw.get("caveat", "")),
            expected=m_raw.get("expected"),
            tolerance=float(m_raw.get("tolerance", 1e-6)),
        )

    tables: dict[str, TableSpec] = {}
    for t_raw in raw.get("tables", []):
        tid = str(t_raw["id"])
        tier = str(t_raw.get("tier", "primary"))
        if tier not in VALID_TIERS:
            raise IRError(f"Table '{tid}' has invalid tier '{tier}'")
        tables[tid] = TableSpec(
            id=tid,
            title=str(t_raw["title"]),
            subtitle=str(t_raw.get("subtitle", "")),
            source=str(t_raw.get("source", "")),
            tier=tier,
            caveat=str(t_raw.get("caveat", "")),
            headers=tuple(str(h) for h in t_raw.get("headers", [])),
            rows=tuple(tuple(str(c) for c in row) for row in t_raw.get("rows", [])),
            highlight_row=t_raw.get("highlight_row"),
            right_align_cols=tuple(int(i) for i in t_raw.get("right_align_cols", [])),
        )

    figures: dict[str, FigureSpec] = {}
    for f_raw in raw.get("figures", []):
        fid = str(f_raw["id"])
        tier = str(f_raw.get("tier", "primary"))
        if tier not in VALID_TIERS:
            raise IRError(f"Figure '{fid}' has invalid tier '{tier}'")
        series_list = tuple(
            FigureSeries(
                label=str(s["label"]),
                values=tuple(s.get("values", [])),
                role=str(s.get("role", "primary")),
                x_values=tuple(s.get("x_values", [])),
                point_labels=tuple(str(p) for p in s.get("point_labels", [])),
            )
            for s in f_raw.get("series", [])
        )
        figures[fid] = FigureSpec(
            id=fid,
            kind=str(f_raw["kind"]),
            title=str(f_raw["title"]),
            subtitle=str(f_raw.get("subtitle", "")),
            source=str(f_raw.get("source", "")),
            alt=str(f_raw.get("alt", "")),
            kicker=str(f_raw.get("kicker", "")),
            accent=str(f_raw.get("accent", "")),
            caption=str(f_raw.get("caption", "")),
            tier=tier,
            caveat=str(f_raw.get("caveat", "")),
            note=str(f_raw.get("note", "")),
            categories=tuple(str(c) for c in f_raw.get("categories", [])),
            series=series_list,
            x_label=str(f_raw.get("x_label", "")),
            x_unit=str(f_raw.get("x_unit", "")),
            x_decimals=int(f_raw.get("x_decimals", 1)),
            x_min=f_raw.get("x_min"),
            x_max=f_raw.get("x_max"),
            x_reference_value=f_raw.get("x_reference_value"),
            x_reference_label=str(f_raw.get("x_reference_label", "")),
            y_label=str(f_raw.get("y_label", "")),
            y_unit=str(f_raw.get("y_unit", "")),
            y_decimals=int(f_raw.get("y_decimals", 2)),
            y_min=f_raw.get("y_min"),
            y_max=f_raw.get("y_max"),
            focus_index=f_raw.get("focus_index"),
            reference_value=f_raw.get("reference_value"),
            reference_label=str(f_raw.get("reference_label", "")),
            nodes=tuple(dict(n) for n in f_raw.get("nodes", [])),
            edges=tuple(dict(e) for e in f_raw.get("edges", [])),
            media_path=str(f_raw.get("media_path", "")),
            media_sha256=str(f_raw.get("media_sha256", "")),
            card_aspect=str(f_raw.get("card_aspect", "16:9")),
        )

    equations: dict[str, EquationSpec] = {}
    for e_raw in raw.get("equations", []):
        eid = str(e_raw["id"])
        equations[eid] = EquationSpec(
            id=eid,
            latex=str(e_raw["latex"]),
            unicode=str(e_raw["unicode"]),
            label=str(e_raw.get("label", "")),
        )

    sections: list[SectionSpec] = []
    for s_raw in raw.get("sections", []):
        sid = str(s_raw["id"])
        tier = str(s_raw.get("tier", "primary"))
        if tier not in VALID_TIERS:
            raise IRError(f"Section '{sid}' has invalid tier '{tier}'")
        title_fallback = str(s_raw.get("title", sid))
        sections.append(
            SectionSpec(
                id=sid,
                preprint_title=str(s_raw.get("preprint_title", title_fallback)),
                monograph_title=str(s_raw.get("monograph_title", title_fallback)),
                level=int(s_raw.get("level", 2)),
                tier=tier,
                caveat=str(s_raw.get("caveat", "")),
                hr_before=bool(s_raw.get("hr_before", False)),
                paragraphs=tuple(str(p) for p in s_raw.get("paragraphs", [])),
                quotes=tuple(str(q) for q in s_raw.get("quotes", [])),
                bullets=tuple(str(b) for b in s_raw.get("bullets", [])),
                post_paragraphs=tuple(str(p) for p in s_raw.get("post_paragraphs", [])),
                callout=str(s_raw.get("callout", "")),
                figure_ids=tuple(str(fid) for fid in s_raw.get("figures", [])),
                table_ids=tuple(str(tid) for tid in s_raw.get("tables", [])),
                equation_ids=tuple(str(eid) for eid in s_raw.get("equations", [])),
            )
        )

    citations = tuple(
        CitationSpec(
            key=str(c["key"]),
            authors=str(c["authors"]),
            year=str(c["year"]),
            title=str(c["title"]),
            venue=str(c.get("venue", "")),
            url=str(c.get("url", "")),
        )
        for c in raw.get("citations", [])
    )

    return ManuscriptIR(
        manifest_path=path,
        base_dir=base_dir,
        meta=meta,
        artifacts=artifacts,
        metrics=metrics,
        sections=tuple(sections),
        tables=tables,
        figures=figures,
        equations=equations,
        citations=citations,
    )


def _load_artifact_json(base_dir: Path, spec: ArtifactSpec) -> tuple[Any, str]:
    art_path = (base_dir / spec.path).resolve()
    if not art_path.is_file():
        raise IRError(f"Artifact '{spec.alias}' file not found: {art_path}")
    raw_bytes = art_path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if spec.sha256 and digest != spec.sha256.lower():
        raise IRError(
            f"Artifact '{spec.alias}' SHA-256 mismatch: expected {spec.sha256}, got {digest}"
        )
    return json.loads(raw_bytes.decode("utf-8")), digest


def resolve_manuscript(ir: ManuscriptIR) -> ResolvedManuscript:
    """Resolve all artifact pointers and derived metrics into verified values."""
    loaded_docs: dict[str, Any] = {}
    artifact_hashes: dict[str, str] = {}
    for alias, spec in ir.artifacts.items():
        doc, digest = _load_artifact_json(ir.base_dir, spec)
        loaded_docs[alias] = doc
        artifact_hashes[alias] = digest

    resolved: dict[str, ResolvedMetric] = {}
    visiting: set[str] = set()

    def _resolve_pointer_str(ptr_expr: str) -> float:
        if "#" not in ptr_expr:
            raise IRError(f"Pointer must use 'alias#/json/pointer' format: '{ptr_expr}'")
        alias, ptr = ptr_expr.split("#", 1)
        if alias not in loaded_docs:
            raise IRError(f"Unknown artifact alias '{alias}' in pointer '{ptr_expr}'")
        val = resolve_json_pointer(loaded_docs[alias], ptr)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise IRError(
                f"Pointer '{ptr_expr}' resolved to non-numeric {type(val).__name__}: {val!r}"
            )
        return float(val)

    def _resolve_metric(mid: str) -> ResolvedMetric:
        if mid in resolved:
            return resolved[mid]
        if mid in visiting:
            raise IRError(f"Cyclic metric dependency involving '{mid}'")
        if mid not in ir.metrics:
            raise IRError(f"Unknown metric '{mid}'")

        visiting.add(mid)
        spec = ir.metrics[mid]
        sources: list[str] = []

        if spec.pointer:
            raw_val = _resolve_pointer_str(spec.pointer)
            sources.append(spec.pointer)
        elif spec.derive:
            if not spec.inputs:
                raise IRError(f"Derived metric '{mid}' requires non-empty 'inputs'")
            vals: list[float] = []
            for inp in spec.inputs:
                if "#" in inp:
                    vals.append(_resolve_pointer_str(inp))
                    sources.append(inp)
                else:
                    dep = _resolve_metric(inp)
                    scale = dep.spec.fmt.scale if dep.spec.derive != "scale" else 1.0
                    vals.append(dep.raw_value * scale)
                    sources.extend(dep.source_pointers)

            op = spec.derive
            if op == "pct_change":
                if len(vals) != 2 or abs(vals[0]) < 1e-15:
                    raise IRError(f"Metric '{mid}' pct_change requires 2 inputs [base, new] with base != 0")
                raw_val = ((vals[1] - vals[0]) / abs(vals[0])) * 100.0
            elif op == "ratio":
                if len(vals) != 2 or abs(vals[1]) < 1e-15:
                    raise IRError(f"Metric '{mid}' ratio requires 2 inputs [num, den] with den != 0")
                raw_val = vals[0] / vals[1]
            elif op == "diff":
                if len(vals) != 2:
                    raise IRError(f"Metric '{mid}' diff requires 2 inputs [a, b]")
                raw_val = vals[0] - vals[1]
            elif op == "sum":
                raw_val = sum(vals)
            elif op == "scale":
                if len(vals) != 1:
                    raise IRError(f"Metric '{mid}' scale requires 1 input")
                raw_val = vals[0] * spec.factor
            elif op == "acos_deg":
                if len(vals) != 1:
                    raise IRError(f"Metric '{mid}' acos_deg requires 1 cosine input in [-1, 1]")
                raw_val = math.degrees(math.acos(max(-1.0, min(1.0, vals[0]))))
            else:
                raise IRError(f"Unsupported derive operation '{op}' on metric '{mid}'")
        else:
            raise IRError(f"Metric '{mid}' must define either 'pointer' or 'derive'")

        if spec.expected is not None:
            if abs(raw_val - float(spec.expected)) > spec.tolerance:
                raise IRError(
                    f"Metric '{mid}' drifted: expected {spec.expected}, resolved {raw_val} "
                    f"(tolerance {spec.tolerance})"
                )

        formatted = fmt_number(raw_val, spec.fmt)
        rm = ResolvedMetric(
            spec=spec,
            raw_value=raw_val,
            formatted=formatted,
            source_pointers=tuple(dict.fromkeys(sources)),
        )
        visiting.remove(mid)
        resolved[mid] = rm
        return rm

    for mid in ir.metrics:
        _resolve_metric(mid)

    return ResolvedManuscript(
        ir=ir,
        artifact_hashes=artifact_hashes,
        metrics=resolved,
    )
