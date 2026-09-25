"""Shared look for every panel: palette, fonts, and small SVG building blocks.

All panels are rendered as standalone SVGs that GitHub shows through an
<img> tag (proxied by camo). That context has hard limits, so every helper
here respects them:

  * no scripts, no external fonts/images/CSS: everything is inline
  * animations are CSS @keyframes (preferred, can be switched off by
    prefers-reduced-motion) or SMIL <animate> where CSS cannot reach (path d)
  * no hover/interaction: an <img> never receives pointer events
  * fonts are whatever the viewer has installed, so text is monospace and
    laid out with a conservative width estimate (MONO_ADVANCE)
"""

from __future__ import annotations

import random
from xml.sax.saxutils import escape

# --- palette -----------------------------------------------------------------
# Neon-on-black, carried over from the previous profile so the identity stays.
BG = "#05020A"          # page black
PANEL = "#0B0714"       # hardware panel face
PANEL_HI = "#140C22"    # top of the panel gradient
EDGE = "#2A1B45"        # panel bevel / hairlines
GRID = "#1A1030"        # faint grid, off-state dots
PURPLE = "#8B2FFF"
CYAN = "#00F6FF"
MAGENTA = "#FF00E6"
TEXT = "#CFE9FF"        # primary text
DIM = "#7D6FA3"         # secondary text / labels
FAINT = "#4A3D6B"       # tertiary text, unlit segments
GREEN = "#39FF88"       # status LED: running
AMBER = "#FFB020"       # status LED: warning / building
RED = "#FF3B5C"         # status LED: stopped

ACCENTS = [CYAN, MAGENTA, PURPLE]

# --- type ---------------------------------------------------------------------
MONO = ("'JetBrains Mono','SFMono-Regular','SF Mono',Menlo,Consolas,"
        "'Liberation Mono','DejaVu Sans Mono',monospace")
# Advance width of one monospace glyph as a fraction of font-size. Real fonts
# sit between 0.55 (Consolas) and 0.61 (Menlo/DejaVu); lay out for the widest.
MONO_ADVANCE = 0.62


def text_width(text: str, size: float) -> float:
    """Worst-case rendered width of `text` in the mono stack at `size` px."""
    return len(text) * size * MONO_ADVANCE


def esc(text: str) -> str:
    """Escape text for use in SVG element content and attribute values."""
    return escape(str(text), {'"': "&quot;"})


def wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap for monospace text."""
    lines, line = [], ""
    for word in str(text).split():
        if line and len(line) + 1 + len(word) > max_chars:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    return lines


def rng(seed: str) -> random.Random:
    """Deterministic randomness, so re-renders only change when data changes."""
    return random.Random(seed)


def fmt(n: float, digits: int = 2) -> str:
    """Compact number formatting for SVG coordinates."""
    s = f"{n:.{digits}f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


# --- document -----------------------------------------------------------------
BASE_CSS = f"""
text{{font-family:{MONO};}}
@media (prefers-reduced-motion: reduce){{
  *{{animation:none!important;transition:none!important;}}
}}
"""


def svg_doc(width: int, height: int, body: str, *, title: str, desc: str = "",
            css: str = "", defs: str = "") -> str:
    """Wrap `body` in a complete, accessible SVG document.

    `width`/`height` become the viewBox; the README decides display size.
    Put @keyframes and classes in `css`; gradients/filters/patterns in `defs`.
    """
    desc_el = f"<desc id='d'>{esc(desc)}</desc>" if desc else ""
    labelled = "t d" if desc else "t"
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
        f"width='{width}' height='{height}' role='img' aria-labelledby='{labelled}' "
        f"fill='none'>"
        f"<title id='t'>{esc(title)}</title>{desc_el}"
        f"<style>{BASE_CSS}{css}</style>"
        f"<defs>{defs}</defs>"
        f"{body}</svg>\n"
    )


# --- defs -----------------------------------------------------------------------
def glow_filter(fid: str, std: float = 3.0, strength: float = 1.0) -> str:
    """Soft neon bloom: blurred copy merged under the source graphic."""
    return (
        f"<filter id='{fid}' x='-50%' y='-50%' width='200%' height='200%' "
        f"color-interpolation-filters='sRGB'>"
        f"<feGaussianBlur in='SourceGraphic' stdDeviation='{fmt(std)}' result='b'/>"
        f"<feComponentTransfer in='b' result='b2'><feFuncA type='linear' slope='{fmt(strength)}'/></feComponentTransfer>"
        f"<feMerge><feMergeNode in='b2'/><feMergeNode in='SourceGraphic'/></feMerge>"
        f"</filter>"
    )


def scanlines_pattern(pid: str, gap: int = 3, opacity: float = 0.18) -> str:
    """Horizontal CRT scanlines; fill a rect with url(#pid) on top of a screen."""
    return (
        f"<pattern id='{pid}' width='4' height='{gap}' patternUnits='userSpaceOnUse'>"
        f"<rect width='4' height='1' fill='#000' opacity='{fmt(opacity)}'/></pattern>"
    )


def panel_gradient(gid: str) -> str:
    return (
        f"<linearGradient id='{gid}' x1='0' y1='0' x2='0' y2='1'>"
        f"<stop offset='0' stop-color='{PANEL_HI}'/><stop offset='1' stop-color='{PANEL}'/>"
        f"</linearGradient>"
    )


def dot_grid_pattern(pid: str, step: int = 12, color: str = GRID) -> str:
    return (
        f"<pattern id='{pid}' width='{step}' height='{step}' patternUnits='userSpaceOnUse'>"
        f"<circle cx='{step / 2}' cy='{step / 2}' r='0.9' fill='{color}'/></pattern>"
    )


# --- hardware parts ---------------------------------------------------------------
def screw(cx: float, cy: float, r: float = 5.0, angle: float = 30.0) -> str:
    """A countersunk panel screw with a slot."""
    return (
        f"<g transform='translate({fmt(cx)} {fmt(cy)}) rotate({fmt(angle)})'>"
        f"<circle r='{fmt(r)}' fill='#1B1230' stroke='{EDGE}' stroke-width='1'/>"
        f"<circle r='{fmt(r * 0.72)}' fill='#120B20'/>"
        f"<rect x='{fmt(-r * 0.62)}' y='-0.8' width='{fmt(r * 1.24)}' height='1.6' rx='0.8' fill='{FAINT}'/>"
        f"</g>"
    )


def panel(x: float, y: float, w: float, h: float, *, r: float = 16,
          fill: str = PANEL, screws: bool = True, stroke: str = EDGE,
          gradient_id: str | None = None) -> str:
    """Rack panel face: rounded body, bevel hairline, optional corner screws.

    Pass `gradient_id` (from panel_gradient in defs) for a lit-from-above face.
    """
    face = f"url(#{gradient_id})" if gradient_id else fill
    out = [
        f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='{fmt(r)}' fill='{face}'/>",
        f"<rect x='{fmt(x + 0.5)}' y='{fmt(y + 0.5)}' width='{fmt(w - 1)}' height='{fmt(h - 1)}' rx='{fmt(r - 0.5)}' stroke='{stroke}' stroke-width='1'/>",
        # top highlight line: reads as a bevel catching light
        f"<path d='M{fmt(x + r)} {fmt(y + 1.5)}H{fmt(x + w - r)}' stroke='#FFFFFF' stroke-opacity='0.06' stroke-width='1'/>",
    ]
    if screws:
        inset = max(12.0, r * 0.9)
        for sx, sy, a in ((x + inset, y + inset, 20), (x + w - inset, y + inset, 75),
                          (x + inset, y + h - inset, 130), (x + w - inset, y + h - inset, 45)):
            out.append(screw(sx, sy, angle=a))
    return "".join(out)


def led(cx: float, cy: float, color: str, *, r: float = 3.2, cls: str = "") -> str:
    """Status LED with a halo. Add a blinking class via `cls` if wanted."""
    c = f" class='{cls}'" if cls else ""
    return (
        f"<g{c}>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='{fmt(r * 2.4)}' fill='{color}' opacity='0.18'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='{fmt(r)}' fill='{color}'/>"
        f"<circle cx='{fmt(cx - r * 0.3)}' cy='{fmt(cy - r * 0.3)}' r='{fmt(r * 0.35)}' fill='#FFFFFF' opacity='0.7'/>"
        f"</g>"
    )


def label(x: float, y: float, text: str, *, size: float = 10, color: str = DIM,
          anchor: str = "start", weight: int = 600, spacing: float = 1.5,
          extra: str = "") -> str:
    """Small uppercase silkscreen label, the kind printed on hardware panels."""
    return (
        f"<text x='{fmt(x)}' y='{fmt(y)}' font-size='{fmt(size)}' fill='{color}' "
        f"text-anchor='{anchor}' font-weight='{weight}' letter-spacing='{fmt(spacing)}'{extra}>"
        f"{esc(str(text).upper())}</text>"
    )
