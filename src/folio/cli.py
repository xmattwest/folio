"""Folio CLI: repository guard, claim verifier, multi-surface compiler, and manifest init."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from folio.figures.raster import rasterize_figure_png, resolve_chrome_bin
from folio.guard import audit_repo
from folio.ir import IRError, load_manifest, resolve_manuscript
from folio.render import (
    render_hf_card_md,
    render_markdown_twin,
    render_monograph,
    render_preprint,
    render_shelltoho_source,
    render_substack,
    render_x_article,
    render_zenodo_json,
)
from folio.verify import verify_manuscript

ALL_TARGETS = ("preprint", "monograph", "substack", "x-article", "syndication")

STARTER_MANIFEST = """# Folio canonical research manifest
base_dir = "."

[meta]
title = "Example Study Title"
subtitle = "Short factual subtitle stating what was measured and found."
author = "Author Name"
date = "2026-11-20"
wordmark = "folio."
abstract = "State the main finding with bound metric {{headline_gain}}."
lede = "State the finding in plain language: {{headline_gain}}."
x_hook = "Short opening finding: {{headline_gain}}."
repo_url = "https://github.com/example/repo"

[artifacts.results]
path = "results.json"

[metrics.headline_gain]
pointer = "results#/summary/gain_pct"
tier = "primary"
style = "percent"
decimals = 1
signed = true

[[sections]]
id = "overview"
preprint_title = "Overview"
monograph_title = "What the experiment found"
paragraphs = [
  "The treatment improved the target metric by {{headline_gain}} over baseline."
]
"""


def _cmd_guard(repo: Path) -> int:
    findings = audit_repo(repo.resolve())
    if findings:
        for item in findings:
            print(f"[FAIL] {item}", file=sys.stderr)
        return 1
    print("[OK] Folio repository hygiene check passed (0 secrets, local paths, or data leaks).")
    return 0


def _cmd_verify(manifest_path: Path) -> int:
    try:
        ir = load_manifest(manifest_path)
        resolved = resolve_manuscript(ir)
    except IRError as exc:
        print(f"[FAIL] IR error: {exc}", file=sys.stderr)
        return 1

    report = verify_manuscript(resolved)
    for finding in report.findings:
        tag = "FAIL" if finding.severity == "error" else "WARN"
        print(f"[{tag}] {finding.location} ({finding.code}): {finding.message}", file=sys.stderr)

    if not report.ok:
        print(
            f"[FAIL] Verification failed with {len(report.errors)} error(s) "
            f"across {report.metrics_verified} metrics.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[OK] Verified {report.metrics_verified} bound metrics across "
        f"{report.artifacts_verified} artifacts (0 errors, {len(report.warnings)} warnings)."
    )
    return 0


def _cmd_build(
    manifest_path: Path,
    out_dir: Path,
    targets: tuple[str, ...],
    no_raster: bool,
    asset_base_url: str,
) -> int:
    try:
        ir = load_manifest(manifest_path)
        resolved = resolve_manuscript(ir)
    except IRError as exc:
        print(f"[FAIL] IR error: {exc}", file=sys.stderr)
        return 1

    report = verify_manuscript(resolved)
    if not report.ok:
        for finding in report.errors:
            print(f"[FAIL] {finding.location} ({finding.code}): {finding.message}", file=sys.stderr)
        print("[FAIL] Build aborted because verification failed.", file=sys.stderr)
        return 1

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy external verified media assets and rasterize 2x PNG cards
    need_substack = "substack" in targets
    need_x = "x-article" in targets
    substack_pngs: dict[str, str] = {}
    x_pngs: dict[str, str] = {}
    media_hashes: dict[str, str] = {}

    for fid, fig in ir.figures.items():
        if fig.kind == "media":
            src_file = (ir.base_dir / fig.media_path).resolve()
            media_hashes[fid] = hashlib.sha256(src_file.read_bytes()).hexdigest()
            fname = src_file.name
            if "preprint" in targets:
                dst = out_dir / "preprint" / "assets" / fname
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_file, dst)
            if "monograph" in targets:
                dst = out_dir / "monograph" / "assets" / fname
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_file, dst)
            if need_substack:
                dst = out_dir / "substack" / "figures" / fname
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_file, dst)
                substack_pngs[fid] = f"figures/{fname}"
            if need_x:
                dst = out_dir / "x-article" / "cards" / fname
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src_file, dst)
                x_pngs[fid] = f"cards/{fname}"

    svg_figures = {fid: fig for fid, fig in ir.figures.items() if fig.kind != "media"}
    if (need_substack or need_x) and not no_raster and svg_figures:
        chrome = resolve_chrome_bin()
        if chrome is None:
            print(
                "[FAIL] Headless Chrome not found for 2x PNG rasterization. "
                "Install Chrome, set CHROME_BIN, or pass --no-raster.",
                file=sys.stderr,
            )
            return 1
        for fid, fig in svg_figures.items():
            if need_substack:
                rel = f"substack/figures/{fid}_2x.png"
                rasterize_figure_png(
                    fig, resolved, out_dir / rel, width=960, height=580, scale_factor=2, chrome_bin=chrome
                )
                substack_pngs[fid] = f"figures/{fid}_2x.png"
            if need_x:
                w, h = (960, 540) if fig.card_aspect == "16:9" else (800, 600)
                aspect_slug = fig.card_aspect.replace(":", "x")
                rel = f"x-article/cards/{fid}_{aspect_slug}.png"
                rasterize_figure_png(
                    fig, resolved, out_dir / rel, width=w, height=h, scale_factor=2, chrome_bin=chrome
                )
                x_pngs[fid] = f"cards/{fid}_{aspect_slug}.png"
    else:
        for fid, fig in svg_figures.items():
            substack_pngs[fid] = f"figures/{fid}_2x.png"
            x_pngs[fid] = f"cards/{fid}_{fig.card_aspect.replace(':', 'x')}.png"

    emitted: list[str] = []
    if "preprint" in targets:
        p = out_dir / "preprint" / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_preprint(resolved), encoding="utf-8")
        emitted.append(str(p))

    if "monograph" in targets:
        p = out_dir / "monograph" / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_monograph(resolved), encoding="utf-8")
        src_p = out_dir / "monograph" / "shelltoho_source.html"
        src_p.write_text(render_shelltoho_source(resolved), encoding="utf-8")
        emitted.extend([str(p), str(src_p)])

    if need_substack:
        p = out_dir / "substack" / "substack_paste_ready.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            render_substack(resolved, substack_pngs, asset_base_url=asset_base_url),
            encoding="utf-8",
        )
        emitted.append(str(p))

    if need_x:
        p = out_dir / "x-article" / "article.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_x_article(resolved, x_pngs), encoding="utf-8")
        emitted.append(str(p))

    if "syndication" in targets:
        syn_dir = out_dir / "syndication"
        syn_dir.mkdir(parents=True, exist_ok=True)
        md_p = syn_dir / "index.md"
        md_p.write_text(render_markdown_twin(resolved), encoding="utf-8")
        zen_p = syn_dir / ".zenodo.json"
        zen_p.write_text(render_zenodo_json(resolved), encoding="utf-8")
        hf_p = syn_dir / "hf_README.md"
        hf_p.write_text(render_hf_card_md(resolved), encoding="utf-8")
        emitted.extend([str(md_p), str(zen_p), str(hf_p)])

    # Write provenance lockfile
    lock = {
        "manifest": str(manifest_path.name),
        "artifacts": resolved.artifact_hashes,
        "media_assets": media_hashes,
        "metrics": {
            mid: {
                "raw_value": rm.raw_value,
                "formatted": rm.formatted,
                "tier": rm.spec.tier,
                "sources": list(rm.source_pointers),
            }
            for mid, rm in resolved.metrics.items()
        },
        "targets": list(targets),
    }
    lock_path = out_dir / "provenance.json"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    emitted.append(str(lock_path))

    print(
        f"[OK] Built {len(targets)} target(s) ({', '.join(targets)}) with "
        f"{report.metrics_verified} verified metrics -> {out_dir}"
    )
    return 0


def _cmd_init(target_dir: Path) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    out = target_dir / "folio.toml"
    if out.exists():
        print(f"[FAIL] {out} already exists.", file=sys.stderr)
        return 1
    out.write_text(STARTER_MANIFEST, encoding="utf-8")
    print(f"[OK] Created starter manifest at {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="folio", description="Folio claim-verified research compiler.")
    parser.add_argument("--version", action="version", version="folio 0.1.0")
    sub = parser.add_subparsers(dest="command")

    guard_p = sub.add_parser("guard", help="Verify tracked repo files contain no secrets or local paths.")
    guard_p.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root to scan.")

    verify_p = sub.add_parser("verify", help="Verify JSON Pointer bindings, epistemic tiers, and Dawn State voice.")
    verify_p.add_argument("manifest", type=Path, help="Path to folio.toml or folio.json manifest.")

    build_p = sub.add_parser("build", help="Verify and compile all publication targets.")
    build_p.add_argument("manifest", type=Path, help="Path to folio.toml or folio.json manifest.")
    build_p.add_argument("--out", type=Path, required=True, help="Output directory for compiled surfaces.")
    build_p.add_argument(
        "--targets",
        type=str,
        default=",".join(ALL_TARGETS),
        help=f"Comma-separated targets from {','.join(ALL_TARGETS)}.",
    )
    build_p.add_argument("--no-raster", action="store_true", help="Skip headless Chrome 2x PNG rasterization.")
    build_p.add_argument("--asset-base-url", type=str, default="", help="Base URL prefix for Substack PNG links.")

    init_p = sub.add_parser("init", help="Create a starter folio.toml manifest in a directory.")
    init_p.add_argument("directory", type=Path, default=Path.cwd(), nargs="?", help="Target directory.")

    args = parser.parse_args(argv)
    if args.command == "guard":
        return _cmd_guard(args.repo)
    if args.command == "verify":
        return _cmd_verify(args.manifest)
    if args.command == "build":
        targets = tuple(t.strip() for t in args.targets.split(",") if t.strip())
        invalid = [t for t in targets if t not in ALL_TARGETS]
        if invalid:
            print(f"[FAIL] Unknown target(s): {', '.join(invalid)}", file=sys.stderr)
            return 1
        return _cmd_build(args.manifest, args.out, targets, args.no_raster, args.asset_base_url)
    if args.command == "init":
        return _cmd_init(args.directory)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
