"""Dual-target figure engine: Dawn State inline SVGs, data drawers, and 2x PNG rasterization."""

from folio.figures.charts import render_figure_svg
from folio.figures.drawer import render_figure_block_html, render_figure_drawer_html
from folio.figures.raster import rasterize_figure_png, resolve_chrome_bin

__all__ = [
    "render_figure_svg",
    "render_figure_drawer_html",
    "render_figure_block_html",
    "rasterize_figure_png",
    "resolve_chrome_bin",
]
