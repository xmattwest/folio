# Folio

**Folio** is a standalone, project-agnostic, claim-verified research compiler. Point it at any external experimental repository to verify every quantitative claim against upstream JSON artifacts and compile four synchronized Dawn State / Warm Precision publication surfaces:

1. **`preprint` (Web Quasi-Publication):** Formal abstract, sticky TOC, numbered sections, equations, verified methodology and negative-result tables, inline SVGs, and citations.
2. **`monograph` (Visual Research Essay):** Narrative thesis headings, bespoke inline semantic `<svg>` diagrams, and collapsible `<details><summary>Text alternative and data</summary>` tables beneath every visual.
3. **`substack` (Substack Paste-Ready Package):** `680px` Charter HTML plus deterministic `2x` Retina PNGs (with zero inline `<svg>` or `<details>` tags).
4. **`x-article` (X Long-Form Article + Card Kit):** Mobile-first beats, clean Unicode math/comparisons (no broken LaTeX), and high-DPI `16:9` / `4:3` Dawn State PNG cards.
5. **`syndication` (Scholar, Zenodo, Hugging Face & Agent Discovery Kit):** Emits a clean RAG/LLM Markdown twin (`index.md`), turnkey DataCite/OAI-PMH deposit record (`.zenodo.json`), Hugging Face Hub Model/Dataset Card stub (`hf_README.md` with `base_model:` YAML frontmatter), and Highwire/Google Scholar `citation_pdf_url`, `citation_doi`, and `citation_author_orcid` metadata.

## Core Subsystems

- **Canonical Evidence IR (`folio.ir`):** Binds every quantitative number via RFC 6901 JSON Pointer (`alias#/path/to/value`) or deterministic derived operations (`pct_change`, `ratio`, `diff`, `sum`, `scale`), with explicit epistemic tiers (`primary`, `exploratory`, `negative`).
- **Deterministic Verifier & Voice Linter (`folio.verify`):** Hard-fails on missing pointers, value drift, unbound quantitative numbers in prose/tables, unframed `exploratory`/`negative` claims, em dashes (`\u2014`), ASCII hyphen-minus on negative numbers, non-sentence figure titles, and banned-slop phrases.
- **Dual-Target Figure Engine (`folio.figures`):** Builds Dawn State inline `<svg>` charts/diagrams + accessible `<details>` data drawers for web outputs and headless-Chrome `2x` Retina PNGs for Substack and X.
- **Public-Repo Hygiene (`folio.guard`):** Scans git-tracked files for API keys, private IPs, local home paths, and accidental research data leaks.

## Installation & Usage

Install as an editable CLI tool so any external research repository can invoke `folio` without copying framework files:

```bash
uv tool install -e .
```

Or run directly inside this repository:

```bash
uv sync --group dev
uv run folio guard
uv run pytest -v
```

### Compiling an External Research Project

From your external research repository (keeping its manifest and outputs completely decoupled from `folio`):

```bash
# Scaffold a starter manifest
folio init docs/

# Verify all JSON Pointer bindings, epistemic tiers, and Dawn State voice rules
folio verify docs/folio.toml

# Compile all four publication targets + 2x Retina PNGs + provenance.json
folio build docs/folio.toml --out runs/folio/
```

## License

MIT
