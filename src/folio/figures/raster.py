"""Deterministic 2x Retina PNG card rasterizer using headless Chrome.

Matches Project Afriat's Warm Precision editorial card aesthetic:
- Pure Ivory (#FFFFF0) canvas with generous whitespace (no top logo stamp or bar)
- Uppercase Inter 600 kicker (0.12em tracking)
- Large Newsreader 600 display headline (-0.04em tracking) with Copper Deep (#96590A) accent phrase
- Crisp Slate Deep (#1E3447) subtitle and two-sided hairline footer
"""

from __future__ import annotations

import html
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from folio.figures.charts import render_figure_svg
from folio.ir import FigureSpec, ResolvedManuscript
from folio.tokens import (
    COPPER_DEEP,
    DAWN_STATE_CSS_VARS,
    GOOGLE_FONTS_LINK,
    IVORY,
    ONYX,
    SLATE_DEEP,
    SLATE_MIST,
)


def resolve_chrome_bin() -> Path | None:
    """Locate a Chrome/Chromium executable for headless 2x PNG rasterization."""
    env_bin = os.environ.get("CHROME_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.is_file():
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return Path(found)
    mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if mac_chrome.is_file():
        return mac_chrome
    return None


def _format_headline_with_accent(title: str, accent: str) -> str:
    clean_title = title.strip()
    if clean_title and clean_title[-1] not in ".!?":
        clean_title = clean_title + "."
    if accent:
        acc_clean = accent.strip()
        if acc_clean in clean_title:
            before, after = clean_title.split(acc_clean, 1)
            return f'{html.escape(before)}<span class="accent">{html.escape(acc_clean)}</span>{html.escape(after)}'
        if acc_clean.rstrip(".") in clean_title:
            key = acc_clean.rstrip(".")
            before, after = clean_title.split(key, 1)
            return f'{html.escape(before)}<span class="accent">{html.escape(key + after)}</span>'
    return html.escape(clean_title)


def _build_card_html(
    fig: FigureSpec,
    resolved: ResolvedManuscript,
    width: int,
    height: int,
) -> str:
    raw_title = resolved.interpolate(fig.title)
    raw_accent = resolved.interpolate(fig.accent) if fig.accent else ""
    headline_html = _format_headline_with_accent(raw_title, raw_accent)
    kicker = html.escape(resolved.interpolate(fig.kicker)) if fig.kicker else ""
    subtitle = html.escape(resolved.interpolate(fig.subtitle))
    source = html.escape(resolved.interpolate(fig.source))
    right_note = html.escape(resolved.interpolate(fig.note)) if fig.note else ""
    svg = render_figure_svg(fig, resolved)

    h1_px = 34 if width >= 920 else 30
    pad = "36px 48px 26px" if width >= 920 else "32px 38px 24px"
    kicker_html = f'<div class="kicker">{kicker}</div>' if kicker else ""
    right_html = f"<span>{right_note}</span>" if right_note else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="{GOOGLE_FONTS_LINK}">
<style>
{DAWN_STATE_CSS_VARS}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: {width}px;
  height: {height}px;
  background: {IVORY};
  color: {ONYX};
  font-family: var(--font-body);
  -webkit-font-smoothing: antialiased;
  overflow: hidden;
}}
.card {{
  width: 100%;
  height: 100%;
  padding: {pad};
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  background: {IVORY};
}}
.head {{
  margin-bottom: 6px;
}}
.kicker {{
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: {SLATE_MIST};
  margin-bottom: 7px;
}}
h1 {{
  font-family: var(--font-display);
  font-size: {h1_px}px;
  font-weight: 600;
  line-height: 1.07;
  letter-spacing: -0.04em;
  color: {ONYX};
  margin-bottom: 7px;
  text-wrap: balance;
}}
h1 .accent {{
  color: {COPPER_DEEP};
}}
.subtitle {{
  font-size: 15.5px;
  line-height: 1.4;
  color: {SLATE_DEEP};
  max-width: 76ch;
}}
.plot {{
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 0;
  margin: 8px 0;
}}
.plot svg {{
  width: 100%;
  max-height: 100%;
}}
.foot {{
  font-size: 12.5px;
  color: {SLATE_MIST};
  border-top: 1px solid rgba(44, 62, 80, 0.18);
  padding-top: 10px;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-variant-numeric: tabular-nums;
}}
</style>
</head>
<body>
<div class="card">
  <div class="head">
    {kicker_html}
    <h1>{headline_html}</h1>
    <p class="subtitle">{subtitle}</p>
  </div>
  <div class="plot">{svg}</div>
  <div class="foot"><span>{source}</span>{right_html}</div>
</div>
</body>
</html>
"""


def rasterize_figure_png(
    fig: FigureSpec,
    resolved: ResolvedManuscript,
    out_path: Path,
    *,
    width: int = 960,
    height: int = 600,
    scale_factor: int = 2,
    chrome_bin: Path | None = None,
) -> Path:
    """Render a Dawn State figure card to a deterministic 2x Retina PNG."""
    chrome = chrome_bin or resolve_chrome_bin()
    if chrome is None:
        raise RuntimeError(
            "Headless Chrome not found. Set CHROME_BIN or pass --no-raster to skip PNG generation."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    card_html = _build_card_html(fig, resolved, width=width, height=height)

    with tempfile.TemporaryDirectory(prefix="folio_raster_") as tmpdir:
        html_path = Path(tmpdir) / f"{fig.id}.html"
        html_path.write_text(card_html, encoding="utf-8")
        cmd = [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            f"--force-device-scale-factor={scale_factor}",
            f"--window-size={width},{height}",
            f"--screenshot={out_path.resolve()}",
            html_path.resolve().as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)

    if not out_path.is_file() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to rasterize PNG for figure '{fig.id}' at {out_path}")
    return out_path
