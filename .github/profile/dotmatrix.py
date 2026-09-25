"""A 5x7 dot-matrix LED font, drawn as SVG circles.

Viewers' installed fonts vary, so anything that has to look exact (the big
name in the hero, numeric readouts) is drawn dot by dot instead of as text.
Each glyph is 5 columns x 7 rows; characters advance 6 columns (1 gap).
"""

from __future__ import annotations

from theme import fmt

COLS, ROWS, ADVANCE = 5, 7, 6

_FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111",
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001",
    "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110",
    "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 10001 01010 00100 00100 00100",
    "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "9": "01110 10001 10001 01111 00001 00010 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000",
    "-": "00000 00000 00000 11111 00000 00000 00000",
    "/": "00001 00001 00010 00100 01000 10000 10000",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    ":": "00000 01100 01100 00000 01100 01100 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000",
    "_": "00000 00000 00000 00000 00000 00000 11111",
    ">": "01000 00100 00010 00001 00010 00100 01000",
    "<": "00010 00100 01000 10000 01000 00100 00010",
    "!": "00100 00100 00100 00100 00100 00000 00100",
    "%": "11000 11001 00010 00100 01000 10011 00011",
    "#": "01010 01010 11111 01010 11111 01010 01010",
    "=": "00000 00000 11111 00000 11111 00000 00000",
}
GLYPHS = {ch: [row for row in rows.split()] for ch, rows in _FONT.items()}


def measure(text: str) -> int:
    """Width of `text` in dot columns (no trailing gap)."""
    return max(0, len(text) * ADVANCE - 1)


def dots(text: str) -> list[tuple[int, int, bool]]:
    """Every dot position of `text` as (col, row, lit). Unknown chars render blank."""
    out = []
    for i, ch in enumerate(str(text).upper()):
        rows = GLYPHS.get(ch, GLYPHS[" "])
        for r, bits in enumerate(rows):
            for c, bit in enumerate(bits):
                out.append((i * ADVANCE + c, r, bit == "1"))
    return out


def render(text: str, x: float, y: float, pitch: float, *, radius: float | None = None,
           lit: str = "#00F6FF", off: str | None = "#1A1030", lit_class: str = "",
           style_fn=None) -> str:
    """Draw `text` with its top-left dot centre at (x, y).

    `pitch` is the centre-to-centre dot spacing; `radius` defaults to 38% of it.
    `off` draws the unlit dots too (the matrix look); pass None to skip them.
    `style_fn(col, row)` may return extra attributes for a lit dot (e.g. a
    per-dot animation-delay), which is how callers stagger power-on effects.
    """
    r = radius if radius is not None else pitch * 0.38
    cls = f" class='{lit_class}'" if lit_class else ""
    unlit, bright = [], []
    for col, row, on in dots(text):
        cx, cy = fmt(x + col * pitch), fmt(y + row * pitch)
        if on:
            extra = style_fn(col, row) if style_fn else ""
            bright.append(f"<circle cx='{cx}' cy='{cy}' r='{fmt(r)}'{cls}{extra}/>")
        elif off:
            unlit.append(f"<circle cx='{cx}' cy='{cy}' r='{fmt(r)}'/>")
    parts = []
    if off and unlit:
        parts.append(f"<g fill='{off}'>{''.join(unlit)}</g>")
    parts.append(f"<g fill='{lit}'>{''.join(bright)}</g>")
    return "".join(parts)
