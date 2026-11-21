"""Unit and integration tests for Folio using small synthetic fixtures."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from folio.cli import main as cli_main
from folio.figures import rasterize_figure_png, render_figure_svg, resolve_chrome_bin
from folio.guard import audit_repo
from folio.ir import IRError, load_manifest, resolve_json_pointer, resolve_manuscript
from folio.render import render_monograph, render_preprint, render_substack, render_x_article
from folio.render.common import render_math_html
from folio.render.x_article import clean_unicode_math
from folio.tokens import EMDASH, MINUS, FormatSpec, fmt_number
from folio.verify import verify_manuscript

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = FIXTURES / "synthetic_manifest.toml"


def test_fmt_number_warm_precision() -> None:
    assert fmt_number(-19.34, FormatSpec(style="percent", decimals=1, signed=True)) == f"{MINUS}19.3%"
    assert fmt_number(12400, FormatSpec(style="int")) == "12,400"
    assert fmt_number(32.14, FormatSpec(style="ratio", decimals=1)) == "32.1x"
    assert fmt_number(None) == "n/a"


def test_json_pointer_resolution() -> None:
    doc = {"a": {"b": [10, {"c/d": 42}]}}
    assert resolve_json_pointer(doc, "/a/b/0") == 10
    assert resolve_json_pointer(doc, "/a/b/1/c~1d") == 42
    with pytest.raises(IRError):
        resolve_json_pointer(doc, "/a/missing")


def test_resolve_and_verify_synthetic_manifest() -> None:
    ir = load_manifest(MANIFEST)
    resolved = resolve_manuscript(ir)
    assert resolved.metrics["kl_pct_drop"].formatted == f"{MINUS}20.0%"
    assert resolved.metrics["k2_ratio"].formatted == "2.0x"

    report = verify_manuscript(resolved)
    assert report.ok, f"Unexpected verification errors: {report.errors}"
    assert report.metrics_verified == 9
    assert report.artifacts_verified == 1


def test_verifier_catches_drift_unbound_emdash_slop_and_titles(tmp_path: Path) -> None:
    # Copy synthetic JSON
    data = json.loads((FIXTURES / "synthetic_results.json").read_text(encoding="utf-8"))
    (tmp_path / "synthetic_results.json").write_text(json.dumps(data), encoding="utf-8")

    bad_manifest = tmp_path / "bad.toml"
    bad_manifest.write_text(
        f"""
base_dir = "."

[meta]
title = "Introducing a Robust Study"
subtitle = "A seamless result {EMDASH} with -5.2% drift."
author = "Test"
date = "2026"

[artifacts.syn]
path = "synthetic_results.json"

[metrics.kl_uniform]
pointer = "syn#/sparsity/uniform_kl"
tier = "exploratory"

[[figures]]
id = "bad_fig"
kind = "bar"
title = "KL Divergence"
subtitle = "Measure in nats"
source = "Source: synthetic."
alt = "Bar chart"
categories = ["Uniform"]

  [[figures.series]]
  label = "KL"
  values = ["{{{{kl_uniform}}}}"]

[[sections]]
id = "s1"
preprint_title = "Results"
monograph_title = "Results"
paragraphs = [
  "Hand-typed 19.3% without binding and leveraged buzzwords."
]
figures = ["bad_fig"]
""",
        encoding="utf-8",
    )

    ir = load_manifest(bad_manifest)
    resolved = resolve_manuscript(ir)
    report = verify_manuscript(resolved)
    codes = {f.code for f in report.errors}

    assert not report.ok
    assert "em_dash" in codes
    assert "ascii_minus" in codes
    assert "unbound_number" in codes
    assert "figure_title_not_sentence" in codes
    assert "missing_epistemic_caveat" in codes
    assert "slop_empty_adjective" in codes
    assert "slop_inflated_verb" in codes
    assert "slop_launch_theatre" in codes


def test_expected_value_drift_hard_fails(tmp_path: Path) -> None:
    (tmp_path / "r.json").write_text('{"x": 0.704}', encoding="utf-8")
    m = tmp_path / "m.toml"
    m.write_text(
        """
[meta]
title = "Drift Test"
subtitle = "Checks expected value"
author = "A"
date = "2026"

[artifacts.r]
path = "r.json"

[metrics.x]
pointer = "r#/x"
tier = "primary"
expected = 0.999
""",
        encoding="utf-8",
    )
    ir = load_manifest(m)
    with pytest.raises(IRError, match="drifted"):
        resolve_manuscript(ir)


def test_render_all_four_surfaces_and_cli(tmp_path: Path) -> None:
    ir = load_manifest(MANIFEST)
    resolved = resolve_manuscript(ir)

    # SVG generation across bar, line, schematic
    for fig in ir.figures.values():
        svg = render_figure_svg(fig, resolved)
        assert "<svg " in svg and "</svg>" in svg

    preprint = render_preprint(resolved)
    assert "Abstract" in preprint
    assert "1 Protected-Boundary Sparsity" in preprint
    assert "<details class=\"figure-data\">" in preprint
    assert "<summary>Text alternative and data</summary>" in preprint
    assert EMDASH not in preprint

    monograph = render_monograph(resolved)
    assert "Preserving the mid-stack cuts divergence" in monograph
    assert "<svg " in monograph
    assert "<details class=\"figure-data\">" in monograph
    assert EMDASH not in monograph

    substack = render_substack(resolved, {"sparsity_bars": "figures/sparsity_bars_2x.png"})
    assert "<svg" not in substack
    assert "<details" not in substack
    assert "figures/sparsity_bars_2x.png" in substack
    assert "max-width: 680px" in substack
    assert EMDASH not in substack

    x_art = render_x_article(resolved, {"sparsity_bars": "cards/sparsity_bars_16x9.png"})
    assert "[Attach Card: cards/sparsity_bars_16x9.png]" in x_art
    assert "$" not in x_art
    assert EMDASH not in x_art
    assert clean_unicode_math(r"$a \times b \rightarrow c$") == "a × b → c"

    # CLI verify & build (--no-raster for fast CI portability)
    assert cli_main(["verify", str(MANIFEST)]) == 0
    out_dir = tmp_path / "compiled"
    assert cli_main(["build", str(MANIFEST), "--out", str(out_dir), "--no-raster"]) == 0
    assert (out_dir / "preprint" / "index.html").is_file()
    assert (out_dir / "monograph" / "index.html").is_file()
    assert (out_dir / "substack" / "substack_paste_ready.html").is_file()
    assert (out_dir / "x-article" / "article.md").is_file()
    assert (out_dir / "provenance.json").is_file()


def test_rasterize_png_if_chrome_available(tmp_path: Path) -> None:
    chrome = resolve_chrome_bin()
    if chrome is None:
        pytest.skip("Headless Chrome not installed in this environment")
    ir = load_manifest(MANIFEST)
    resolved = resolve_manuscript(ir)
    png_path = tmp_path / "sparsity_bars_2x.png"
    rasterize_figure_png(ir.figures["sparsity_bars"], resolved, png_path, width=960, height=540, chrome_bin=chrome)
    raw = png_path.read_bytes()
    # Verify PNG magic header
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(raw) > 5_000


def test_guard_blocks_secrets_and_local_paths(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    leaky = tmp_path / "leak.txt"
    fake_key = "sk-" + "1234567890" + "abcdefghijklmnop"
    fake_path = "/home" + "/alice/project/"
    leaky.write_text(f"token = {fake_key}\npath = {fake_path}\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "leak.txt"], check=True)
    findings = audit_repo(tmp_path)
    assert any("openai_or_api_key" in f for f in findings)
    assert any("local_home_path" in f for f in findings)


def test_solo_author_pronoun_lint_and_shelltoho_features(tmp_path: Path) -> None:
    (tmp_path / "r.json").write_text('{"acc": 0.258, "mem": 23.08}', encoding="utf-8")
    bad_solo = tmp_path / "solo.toml"
    bad_solo.write_text(
        """
[meta]
title = "Solo Essay"
subtitle = "Testing first-person voice."
author = "Matt West"
date = "November 2026"

[artifacts.r]
path = "r.json"

[metrics.acc_pct]
derive = "scale"
inputs = ["r#/acc"]
factor = 100.0
tier = "primary"
style = "percent"
decimals = 1

[metrics.mem_gb]
pointer = "r#/mem"
tier = "primary"
decimals = 2
unit = "GB"

[[figures]]
id = "pareto"
kind = "scatter"
title = "Compression fits on a 24 GB card while lifting accuracy to {{acc_pct}}"
accent = "lifting accuracy to {{acc_pct}}"
subtitle = "Accuracy (%) vs. storage (GB)"
source = "Source: r.json."
alt = "Scatter plot at {{mem_gb}} and {{acc_pct}}."
x_min = 0.0
x_max = 70.0
x_reference_value = 24.0
x_reference_label = "24 GB single-GPU ceiling"
y_unit = "%"

  [[figures.series]]
  label = "Runs"
  x_values = ["{{mem_gb}}"]
  values = ["{{acc_pct}}"]
  point_labels = ["Compact ({{acc_pct}})"]

[[sections]]
id = "s1"
preprint_title = "Method"
monograph_title = "Method"
paragraphs = [
  "We tested the model at {{mem_gb}} and reached {{acc_pct}}."
]
quotes = [
  "Quoted model output saying \\"we accept\\" is allowed, unlike unquoted narrator pronouns."
]
figures = ["pareto"]
""",
        encoding="utf-8",
    )
    ir_bad = load_manifest(bad_solo)
    res_bad = resolve_manuscript(ir_bad)
    rep_bad = verify_manuscript(res_bad)
    assert any(f.code == "solo_author_plural_pronoun" and "paragraphs[0]" in f.location for f in rep_bad.errors)
    assert not any("quotes[0]" in f.location for f in rep_bad.errors)

    # Fix narrator pronoun to "I", add slope + self-loop schematic, and verify clean build
    good_solo = tmp_path / "solo_ok.toml"
    good_solo.write_text(
        bad_solo.read_text(encoding="utf-8").replace("We tested", "I tested")
        + """
[[equations]]
id = "eq1"
latex = "R_{\\\\mathrm{safe}} = R_{\\\\mathrm{proc}}(I - Q_{42}Q_{42}^\\\\top)"
unicode = "R_safe = R_proc (I \u2212 Q_42 Q_42^T)"
label = "1"

[[figures]]
id = "paired_slope"
kind = "slope"
title = "Distillation lifts accuracy to {{acc_pct}}"
subtitle = "Before vs. after (%)"
source = "Source: r.json."
alt = "Slope to {{acc_pct}}."
categories = ["Pass 1", "Pass 2"]
y_unit = "%"

  [[figures.series]]
  label = "Multi-hop"
  role = "focus"
  values = ["{{acc_pct}}", "{{acc_pct}}"]
""",
        encoding="utf-8",
    )
    ir_ok = load_manifest(good_solo)
    res_ok = resolve_manuscript(ir_ok)
    assert res_ok.metric_value("{{acc_pct}}") == pytest.approx(25.8)
    rep_ok = verify_manuscript(res_ok)
    assert rep_ok.ok, f"Unexpected errors: {rep_ok.errors}"

    mono = render_monograph(res_ok)
    assert 'class="reader-sidebar"' in mono
    assert "data-reader-section" in mono
    assert "<blockquote>" in mono
    assert "80.0" not in mono  # scatter ticks bounded by x_max = 70.0
    assert "<sup>\u22a4</sup>" in render_math_html("R_proc = U V^T")


def test_media_figure_acos_deg_and_hero_placement(tmp_path: Path) -> None:
    import hashlib

    (tmp_path / "r.json").write_text('{"cos": 0.0514, "acc": 25.8}', encoding="utf-8")
    # Minimal valid 1x1 GIF89a header
    gif_bytes = b"GIF89a\x08\x00\x04\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x08\x00\x04\x00\x00\x02\x02D\x01\x00;"
    (tmp_path / "anim.gif").write_bytes(gif_bytes)
    gif_sha = hashlib.sha256(gif_bytes).hexdigest()

    m = tmp_path / "media.toml"
    m.write_text(
        f"""
[meta]
title = "Rotating the Bottleneck"
subtitle = "Twists {{{{angle}}}} across depth."
author = "Matt West"
date = "November 2026"
hero_figure = "hero_anim"
opening_paragraphs = ["The manifold rotates {{{{angle}}}} across depth."]

[artifacts.r]
path = "r.json"

[metrics.angle]
derive = "acos_deg"
inputs = ["r#/cos"]
tier = "primary"
decimals = 1
unit = "\u00b0"

[metrics.acc]
pointer = "r#/acc"
tier = "primary"
style = "percent"
decimals = 1

[[figures]]
id = "hero_anim"
kind = "media"
media_path = "anim.gif"
media_sha256 = "{gif_sha}"
title = "Procrustes untwists an {{{{angle}}}} rotation to reach {{{{acc}}}}"
subtitle = "3D trajectory"
caption = "Realigns the {{{{angle}}}} turn."
source = "Source: r.json."
alt = "Animated GIF showing {{{{angle}}}} rotation."

[[sections]]
id = "s1"
preprint_title = "Procrustes Alignment"
monograph_title = "Zero Shared Neurons, One Shared Direction"
paragraphs = ["Accuracy reaches {{{{acc}}}} after untwisting {{{{angle}}}}."]
figures = ["hero_anim"]
""",
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert cli_main(["build", str(m), "--out", str(out), "--no-raster"]) == 0
    assert (out / "monograph" / "assets" / "anim.gif").is_file()
    assert (out / "preprint" / "assets" / "anim.gif").is_file()
    assert (out / "substack" / "figures" / "anim.gif").is_file()
    assert (out / "x-article" / "cards" / "anim.gif").is_file()

    mono = (out / "monograph" / "index.html").read_text(encoding="utf-8")
    assert mono.count('src="assets/anim.gif"') == 1
    assert 'width="8" height="4"' in mono
    assert "87.1\u00b0" in mono


