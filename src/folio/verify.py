"""Deterministic claim verifier and Dawn State editorial voice linter."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from folio.ir import METRIC_TOKEN_RE, ResolvedManuscript
from folio.tokens import EMDASH

# Banned-slop patterns derived directly from Warm Precision VOICE.md
SLOP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "inflated_verb",
        re.compile(
            r"\b(?:spearheaded|leveraged|synergized|elevated|empowered|unlocked|revolutionized|transformed)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "empty_adjective",
        re.compile(
            r"\b(?:robust|seamless|cutting-edge|holistic|dynamic|pivotal|passionate|world-class|powerful)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "stock_frame",
        re.compile(
            r"(?:in today's fast-paced world|it's not just\b|here's the thing|let's dive in|the result\?|game-changer|at the intersection of)",
            re.IGNORECASE,
        ),
    ),
    (
        "hedge_stack",
        re.compile(
            r"\b(?:may potentially|could possibly|it is important to note that)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "launch_theatre",
        re.compile(r"^\s*introducing\b", re.IGNORECASE),
    ),
)

SOLO_PLURAL_RE = re.compile(r"\b(?:we|our|ours)\b", re.IGNORECASE)

# ASCII hyphen used as minus sign before a numeric literal
ASCII_MINUS_NUM_RE = re.compile(r"(?<![A-Za-z0-9/])-\d+(?:\.\d+)?(?:%|x|pp|GB|MB|ms|nats)?\b")

# Quantitative numbers in uninterpolated templates that should be bound via {{metric_id}}
QUANT_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_#/.\-])"
    r"(?:"
    r"[\+\-\u2212]?\$\d[\d,]*(?:\.\d+)?[KMBkmb]?"
    r"|[\+\-\u2212]?\d[\d,]*(?:\.\d+)?%"
    r"|[\+\-\u2212]?\d+\.\d+(?:[eE][\+\-\u2212]?\d+)?"
    r"|[\+\-\u2212]?\d+(?:\.\d+)?\s*(?:pp|nats|GB|MB|KB|ms|ms/item|Hz|FLOPs|\u00b0)"
    r"|[\+\-\u2212]\d+(?:\.\d+)?"
    r")"
    r"(?![A-Za-z0-9_])"
)

# Structural / naming tokens exempted from unbound-number checks
STRUCTURAL_EXEMPT_RE = re.compile(
    r"(?:"
    r"https?://\S+"
    r"|arXiv:\d{4}\.\d{4,5}"
    r"|\b(?:L\d+(?:\.\.L?\d+)?|Layer\s+\d+(?:\s+to\s+(?:Layer\s+)?\d+)?|Layers\s+\d+\s+to\s+\d+|K\s*=\s*\d+(?:\.\.\d+)?)"
    r"|\b(?:INT4|INT8|FP8|FP16|FP32|BF16|W4A16|W8A16|0-CoT|\d+-hop|\d+-pass|\d+-bit)\b"
    r"|\b(?:0%(?:-APR)?[\s\-]+(?:interest[\s\-]+)?(?:loan|debt|payable)s?|0%-APR)\b"
    r"|\b\d+\s*GB\s+(?:single-GPU\s+)?(?:GPU|card|VRAM|workstation|Mac|ceiling)\b"
    r"|\b(?:Gemma\s+\d+(?:\.\d+)?(?:\s+\d+B)?|Llama\s+\d+(?:\.\d+)?(?:\s+\d+B)?|Qwen\s*\d+(?:\.\d+)?(?:-?\d+B)?|Phi-\d+(?:\s+\d+B)?|Inkling(?:-|\s+)\d+(?:-|\s+)Mini)"
    r"|\b(?:Phase|Part|Section|Table|Figure|Fig\.|Action|Stage|Step)\s+\d+(?:\.\d+)?"
    r"|\b(?:19|20)\d{2}\b"
    r"|`[^`]+`"
    r")",
    re.IGNORECASE,
)

# Finite verbs / statement predicates indicating a continuous finding title
FINDING_VERB_RE = re.compile(
    r"\b(?:"
    r"is|are|was|were|be|has|have|had|does|do|did|can|will|"
    r"beats?|cuts?|drops?|falls?|rises?|lifts?|scales?|shrinks?|doubles?|triples?|"
    r"reduces?|increases?|improves?|lowers?|raises?|shifts?|moves?|triggers?|drives?|"
    r"causes?|prevents?|preserves?|converges?|diverges?|matches?|exceeds?|outperforms?|"
    r"recovers?|heals?|eliminates?|collapses?|fails?|holds?|remains?|shows?|reveals?|"
    r"separates?|aligns?|rotates?|trims?|scrubs?|flips?|tracks?|retains?|leaves?|"
    r"reaches?|achieves?|requires?|needs?|loses?|gains?|cancels?|amplifies?|"
    r"feeds?|routes?|projects?|maps?|writes?|reads?|compresses?|prunes?|quantizes?|"
    r"folds?|clamps?|decodes?|encodes?|peaks?|cools?|spikes?|runs?|fits?|sits?|"
    r"passes?|loops?|bridges?|anchors?|breaks?|blocks?|stops?|keeps?|takes?|gives?|"
    r"makes?|turns?|uses?|adds?|removes?|splits?|merges?|combines?|concentrates?|"
    r"activates?|suppresses?|forgives?|prices?|erases?|restores?|solves?|explains?|"
    r"wrecks?|starves?|misses?|cures?|unlocks?|packs?|untwists?|twists?"
    r")\b",
    re.IGNORECASE,
)

EPISTEMIC_QUALIFIER_RE = re.compile(
    r"\b(?:exploratory|preliminary|negative|null|failed|did not|does not|caveat|limit|boundary|untrained|extrapolat)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LintFinding:
    severity: str  # error | warning
    code: str
    location: str
    message: str


@dataclass(frozen=True)
class VerificationReport:
    findings: tuple[LintFinding, ...]
    metrics_verified: int
    artifacts_verified: int

    @property
    def ok(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.severity == "warning"]


def _is_solo_real_author(author: str) -> bool:
    a = author.strip()
    if not a:
        return False
    low = a.lower()
    if any(tok in low for tok in (" and ", ",", "&", "et al", "test", "example", "author")):
        return False
    return True


def _check_text_rules(
    raw_text: str,
    rendered_text: str,
    location: str,
    allow_numbers: set[str],
    findings: list[LintFinding],
    check_unbound: bool = True,
    solo_author: bool = False,
) -> None:
    if not raw_text:
        return

    # 1. Em dash prohibition
    if EMDASH in rendered_text:
        findings.append(
            LintFinding(
                severity="error",
                code="em_dash",
                location=location,
                message="Em dash (U+2014) is forbidden by Dawn State editorial rules; use a period, comma, colon, or parentheses.",
            )
        )

    # 2. ASCII hyphen-minus on negative numbers (strip code spans and URLs first)
    cleaned_rendered = re.sub(r"`[^`]+`|https?://\S+", "", rendered_text)
    for m in ASCII_MINUS_NUM_RE.finditer(cleaned_rendered):
        findings.append(
            LintFinding(
                severity="error",
                code="ascii_minus",
                location=location,
                message=f"Use true Unicode minus (U+2212) instead of ASCII hyphen in '{m.group(0)}'.",
            )
        )

    # 3. Banned slop phrases
    for label, pat in SLOP_PATTERNS:
        m = pat.search(rendered_text)
        if m:
            findings.append(
                LintFinding(
                    severity="error",
                    code=f"slop_{label}",
                    location=location,
                    message=f"Banned Dawn State voice phrase ({label}): '{m.group(0)}'.",
                )
            )

    # 4. Solo-author royal "we" check (outside quoted model transcripts)
    if solo_author:
        unquoted = re.sub(r'"[^"]*"|\*[^*]+\*|`[^`]+`', "", rendered_text)
        m_we = SOLO_PLURAL_RE.search(unquoted)
        if m_we:
            findings.append(
                LintFinding(
                    severity="error",
                    code="solo_author_plural_pronoun",
                    location=location,
                    message=f"Solo-author manuscript uses plural pronoun '{m_we.group(0)}'; use first-person singular ('I') or direct active phrasing.",
                )
            )

    # 5. Unbound quantitative numbers in pre-interpolation template
    if check_unbound:
        stripped = METRIC_TOKEN_RE.sub("", raw_text)
        stripped = STRUCTURAL_EXEMPT_RE.sub("", stripped)
        for m in QUANT_NUMBER_RE.finditer(stripped):
            token = m.group(0).strip()
            if token in allow_numbers:
                continue
            findings.append(
                LintFinding(
                    severity="error",
                    code="unbound_number",
                    location=location,
                    message=f"Unbound quantitative number '{token}' must reference a JSON Pointer metric via {{{{metric_id}}}}.",
                )
            )


def _check_figure_title(rendered_title: str, location: str, findings: list[LintFinding]) -> None:
    words = [w for w in re.split(r"\s+", rendered_title.strip()) if w]
    if len(words) < 4 or not FINDING_VERB_RE.search(rendered_title):
        findings.append(
            LintFinding(
                severity="error",
                code="figure_title_not_sentence",
                location=location,
                message=(
                    f"Figure title must state the finding as a continuous sentence with a verb, "
                    f"not a bare label: '{rendered_title}'."
                ),
            )
        )


def verify_manuscript(resolved: ResolvedManuscript) -> VerificationReport:
    """Run all deterministic provenance, epistemic, and Dawn State editorial checks."""
    ir = resolved.ir
    findings: list[LintFinding] = []
    allow_numbers = set(ir.meta.allow_numbers)
    solo_author = _is_solo_real_author(ir.meta.author)

    def _safe_interp(raw: str, loc: str) -> str:
        try:
            return resolved.interpolate(raw)
        except Exception as exc:
            findings.append(
                LintFinding(severity="error", code="unresolved_metric", location=loc, message=str(exc))
            )
            return raw

    # Meta fields
    meta_fields = [
        ("meta.title", ir.meta.title, True),
        ("meta.subtitle", ir.meta.subtitle, True),
        ("meta.preprint_title", ir.meta.preprint_title, True),
        ("meta.monograph_title", ir.meta.monograph_title, True),
        ("meta.substack_title_alt", ir.meta.substack_title_alt, True),
        ("meta.abstract", ir.meta.abstract, True),
        ("meta.lede", ir.meta.lede, True),
        ("meta.x_hook", ir.meta.x_hook, True),
        ("meta.ai_disclosure", ir.meta.ai_disclosure, False),
    ]
    for loc, raw, check_unbound in meta_fields:
        if not raw:
            continue
        rendered = _safe_interp(raw, loc)
        _check_text_rules(
            raw,
            rendered,
            loc,
            allow_numbers,
            findings,
            check_unbound=check_unbound,
            solo_author=solo_author and check_unbound,
        )

        # Headline slots must not silently promote exploratory/negative metrics
        if loc in ("meta.title", "meta.subtitle", "meta.x_hook"):
            for m in METRIC_TOKEN_RE.finditer(raw):
                mid = m.group(1)
                if mid in resolved.metrics and resolved.metrics[mid].spec.tier in ("exploratory", "negative"):
                    if not EPISTEMIC_QUALIFIER_RE.search(rendered):
                        findings.append(
                            LintFinding(
                                severity="error",
                                code="unframed_headline_tier",
                                location=loc,
                                message=(
                                    f"{resolved.metrics[mid].spec.tier.capitalize()} metric '{mid}' used in "
                                    f"headline slot '{loc}' without explicit framing."
                                ),
                            )
                        )

    for idx, item in enumerate(ir.meta.opening_paragraphs):
        loc = f"meta.opening_paragraphs[{idx}]"
        rendered = _safe_interp(item, loc)
        _check_text_rules(item, rendered, loc, allow_numbers, findings, solo_author=solo_author)

    for idx, item in enumerate(ir.meta.opening_summary):
        loc = f"meta.opening_summary[{idx}]"
        rendered = _safe_interp(item, loc)
        _check_text_rules(item, rendered, loc, allow_numbers, findings, solo_author=solo_author)

    if ir.meta.hero_figure and ir.meta.hero_figure not in ir.figures:
        findings.append(
            LintFinding(
                severity="error",
                code="missing_hero_figure_ref",
                location="meta.hero_figure",
                message=f"meta.hero_figure references unknown figure '{ir.meta.hero_figure}'.",
            )
        )

    # Metric-level epistemic framing
    for mid, rm in resolved.metrics.items():
        if rm.spec.tier in ("exploratory", "negative") and not rm.spec.caveat.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_epistemic_caveat",
                    location=f"metrics.{mid}",
                    message=f"Metric '{mid}' has tier '{rm.spec.tier}' and requires an explicit non-empty 'caveat'.",
                )
            )

    # Sections
    for sec in ir.sections:
        sloc = f"sections.{sec.id}"
        if sec.tier in ("exploratory", "negative") and not sec.caveat.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_section_caveat",
                    location=sloc,
                    message=f"Section '{sec.id}' has tier '{sec.tier}' and requires an explicit 'caveat'.",
                )
            )
        for field_name, raw in (
            ("preprint_title", sec.preprint_title),
            ("monograph_title", sec.monograph_title),
            ("callout", sec.callout),
            ("caveat", sec.caveat),
        ):
            if raw:
                rendered = _safe_interp(raw, f"{sloc}.{field_name}")
                _check_text_rules(raw, rendered, f"{sloc}.{field_name}", allow_numbers, findings, solo_author=solo_author)

        for idx, para in enumerate(sec.paragraphs):
            loc = f"{sloc}.paragraphs[{idx}]"
            rendered = _safe_interp(para, loc)
            _check_text_rules(para, rendered, loc, allow_numbers, findings, solo_author=solo_author)

        for idx, quote in enumerate(sec.quotes):
            loc = f"{sloc}.quotes[{idx}]"
            rendered = _safe_interp(quote, loc)
            _check_text_rules(quote, rendered, loc, allow_numbers, findings, solo_author=solo_author)

        for idx, bullet in enumerate(sec.bullets):
            loc = f"{sloc}.bullets[{idx}]"
            rendered = _safe_interp(bullet, loc)
            _check_text_rules(bullet, rendered, loc, allow_numbers, findings, solo_author=solo_author)

        for idx, para in enumerate(sec.post_paragraphs):
            loc = f"{sloc}.post_paragraphs[{idx}]"
            rendered = _safe_interp(para, loc)
            _check_text_rules(para, rendered, loc, allow_numbers, findings, solo_author=solo_author)

        for fid in sec.figure_ids:
            if fid not in ir.figures:
                findings.append(
                    LintFinding(
                        severity="error",
                        code="missing_figure_ref",
                        location=sloc,
                        message=f"Section '{sec.id}' references unknown figure '{fid}'.",
                    )
                )
        for tid in sec.table_ids:
            if tid not in ir.tables:
                findings.append(
                    LintFinding(
                        severity="error",
                        code="missing_table_ref",
                        location=sloc,
                        message=f"Section '{sec.id}' references unknown table '{tid}'.",
                    )
                )
        for eid in sec.equation_ids:
            if eid not in ir.equations:
                findings.append(
                    LintFinding(
                        severity="error",
                        code="missing_equation_ref",
                        location=sloc,
                        message=f"Section '{sec.id}' references unknown equation '{eid}'.",
                    )
                )

    # Tables
    for tid, tbl in ir.tables.items():
        tloc = f"tables.{tid}"
        if tbl.tier in ("exploratory", "negative") and not tbl.caveat.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_table_caveat",
                    location=tloc,
                    message=f"Table '{tid}' has tier '{tbl.tier}' and requires an explicit 'caveat'.",
                )
            )
        for field_name, raw in (
            ("title", tbl.title),
            ("subtitle", tbl.subtitle),
            ("source", tbl.source),
            ("caveat", tbl.caveat),
        ):
            if raw:
                rendered = _safe_interp(raw, f"{tloc}.{field_name}")
                _check_text_rules(
                    raw,
                    rendered,
                    f"{tloc}.{field_name}",
                    allow_numbers,
                    findings,
                    check_unbound=(field_name != "source"),
                    solo_author=solo_author,
                )
        for r_idx, row in enumerate(tbl.rows):
            for c_idx, cell in enumerate(row):
                loc = f"{tloc}.rows[{r_idx}][{c_idx}]"
                rendered = _safe_interp(cell, loc)
                _check_text_rules(cell, rendered, loc, allow_numbers, findings, solo_author=solo_author)

    # Figures
    for fid, fig in ir.figures.items():
        floc = f"figures.{fid}"
        if fig.kind == "media":
            if not fig.media_path.strip():
                findings.append(
                    LintFinding(
                        severity="error",
                        code="missing_media_path",
                        location=floc,
                        message=f"Media figure '{fid}' requires a non-empty 'media_path'.",
                    )
                )
            else:
                mpath = (ir.base_dir / fig.media_path).resolve()
                if not mpath.is_file():
                    findings.append(
                        LintFinding(
                            severity="error",
                            code="missing_media_file",
                            location=f"{floc}.media_path",
                            message=f"Media file not found for figure '{fid}': {mpath}",
                        )
                    )
                elif fig.media_sha256:
                    digest = hashlib.sha256(mpath.read_bytes()).hexdigest()
                    if digest != fig.media_sha256.lower():
                        findings.append(
                            LintFinding(
                                severity="error",
                                code="media_sha256_mismatch",
                                location=f"{floc}.media_sha256",
                                message=f"Media '{fid}' SHA-256 mismatch: expected {fig.media_sha256}, got {digest}",
                            )
                        )
        if fig.tier in ("exploratory", "negative") and not fig.caveat.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_figure_caveat",
                    location=floc,
                    message=f"Figure '{fid}' has tier '{fig.tier}' and requires an explicit 'caveat'.",
                )
            )
        if not fig.subtitle.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_figure_subtitle",
                    location=floc,
                    message=f"Figure '{fid}' requires a subtitle stating measure, unit, and sample.",
                )
            )
        if not fig.source.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_figure_source",
                    location=floc,
                    message=f"Figure '{fid}' requires a source line.",
                )
            )
        if not fig.alt.strip():
            findings.append(
                LintFinding(
                    severity="error",
                    code="missing_figure_alt",
                    location=floc,
                    message=f"Figure '{fid}' requires non-empty alt text for accessibility.",
                )
            )

        rendered_title = _safe_interp(fig.title, f"{floc}.title")
        _check_text_rules(fig.title, rendered_title, f"{floc}.title", allow_numbers, findings, solo_author=solo_author)
        _check_figure_title(rendered_title, f"{floc}.title", findings)

        for field_name, raw in (
            ("kicker", fig.kicker),
            ("subtitle", fig.subtitle),
            ("caption", fig.caption),
            ("source", fig.source),
            ("alt", fig.alt),
            ("note", fig.note),
            ("caveat", fig.caveat),
        ):
            if raw:
                rendered = _safe_interp(raw, f"{floc}.{field_name}")
                _check_text_rules(
                    raw,
                    rendered,
                    f"{floc}.{field_name}",
                    allow_numbers,
                    findings,
                    check_unbound=(field_name not in ("source", "kicker")),
                    solo_author=solo_author,
                )

        for n_idx, node in enumerate(fig.nodes):
            for nf in ("label", "sublabel"):
                raw_nf = str(node.get(nf, ""))
                if raw_nf:
                    r_nf = _safe_interp(raw_nf, f"{floc}.nodes[{n_idx}].{nf}")
                    _check_text_rules(
                        raw_nf, r_nf, f"{floc}.nodes[{n_idx}].{nf}", allow_numbers, findings, check_unbound=False, solo_author=solo_author
                    )

        for e_idx, edge in enumerate(fig.edges):
            raw_el = str(edge.get("label", ""))
            if raw_el:
                r_el = _safe_interp(raw_el, f"{floc}.edges[{e_idx}].label")
                _check_text_rules(
                    raw_el, r_el, f"{floc}.edges[{e_idx}].label", allow_numbers, findings, check_unbound=False, solo_author=solo_author
                )

        # Verify all series values (and optional x_values) resolve
        for s_idx, series in enumerate(fig.series):
            for v_idx, val in enumerate(series.values):
                try:
                    resolved.metric_value(val)
                except Exception as exc:
                    findings.append(
                        LintFinding(
                            severity="error",
                            code="unresolved_figure_value",
                            location=f"{floc}.series[{s_idx}].values[{v_idx}]",
                            message=str(exc),
                        )
                    )
            for x_idx, xval in enumerate(series.x_values):
                try:
                    resolved.metric_value(xval)
                except Exception as exc:
                    findings.append(
                        LintFinding(
                            severity="error",
                            code="unresolved_figure_x_value",
                            location=f"{floc}.series[{s_idx}].x_values[{x_idx}]",
                            message=str(exc),
                        )
                    )

    return VerificationReport(
        findings=tuple(findings),
        metrics_verified=len(resolved.metrics),
        artifacts_verified=len(resolved.artifact_hashes),
    )
