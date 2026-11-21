# Folio

**Folio** is a claim-verified research compiler that turns experimental repositories (structured JSON results, scripts, and lab notes) into four synchronized publication formats:

1. **Web Preprint / Quasi-Publication**: Formal academic-grade HTML with citations, sticky TOC, mathematical notation, and verified figure tables.
2. **Visual Research Monograph**: Narrative thesis sections paired with inline semantic `<svg>` diagrams and collapsible `<details>` data drawers.
3. **Substack Paste-Ready Package**: `680px` Charter HTML plus high-DPI `2x` PNG figure rasterizations ready for Substack's editor.
4. **X Long-Form Article + Card Kit**: High-contrast social cards (`16:9` / `4:3`), Unicode math, and mobile-first structural beats.

## Core Design Principles

- **Canonical Evidence IR**: Every quantitative claim binds via JSON Pointer to an upstream result artifact with an explicit epistemic tier (`primary`, `exploratory`, `negative`).
- **Deterministic Claim & Voice Verification**: Automated audits verify numeric provenance before rendering and enforce clean editorial typography.
- **Strict Framework Boundary**: Folio contains zero project-specific data, weights, or credentials. Point `folio` at any external research directory to compile outputs locally.

## Quickstart

```bash
uv sync
uv run folio guard
```

## License

MIT
