"""Low-resolution dithered pixel canvas, written out as an indexed PNG.

Everything on the profile is drawn here: a small grid of palette indices,
ordered (Bayer) dithering between neighbouring palette colours, a 5x7
bitmap font, hash-based noise, and an animated-PNG encoder. Standard library only.
"""

from __future__ import annotations

import math
import struct
import zlib

# One palette for every panel. Index order matters only to the ramps below.
PALETTE = [
    (0x0A, 0x0C, 0x12),  # 0 ink
    (0x14, 0x20, 0x3A),  # 1 night
    (0x25, 0x41, 0x70),  # 2 navy
    (0x52, 0x82, 0xB8),  # 3 blue
    (0xD9, 0x62, 0x2B),  # 4 ember
    (0xF0, 0xB8, 0x77),  # 5 sand
    (0xEF, 0xE9, 0xDC),  # 6 bone
    (0x5F, 0xD4, 0x9A),  # 7 green: the aurora, nothing else
]
INK, NIGHT, NAVY, BLUE, EMBER, SAND, BONE, GREEN = range(8)

SCALE = 4  # each canvas pixel becomes SCALE x SCALE in the PNG


def _bayer(n: int) -> list[list[int]]:
    m = [[0]]
    while len(m) < n:
        s = len(m)
        m = [[4 * m[y % s][x % s] + ((0, 2), (3, 1))[y // s][x // s]
              for x in range(2 * s)] for y in range(2 * s)]
    return m


_B8 = _bayer(8)


def threshold(x: int, y: int) -> float:
    """Ordered-dither threshold in (0, 1) for canvas pixel (x, y)."""
    return (_B8[y & 7][x & 7] + 0.5) / 64.0


def ramp(t: float, colours: list[int], x: int, y: int) -> int:
    """Pick a palette index for tone t in [0, 1] along `colours`, dithered."""
    t = min(1.0, max(0.0, t)) * (len(colours) - 1)
    i = min(int(t), len(colours) - 2)
    return colours[i + 1] if (t - i) > threshold(x, y) else colours[i]


# --- noise -------------------------------------------------------------------------
def hash01(*ints: int) -> float:
    """Deterministic pseudo-random float in [0, 1) from integers."""
    h = 0x9E3779B9
    for v in ints:
        h ^= (v & 0xFFFFFFFF) + 0x85EBCA6B + ((h << 6) & 0xFFFFFFFF) + (h >> 2)
        h = (h * 0xC2B2AE35) & 0xFFFFFFFF
        h ^= h >> 15
    return h / 0x100000000


def _smooth(t: float) -> float:
    return t * t * (3 - 2 * t)


def noise2(x: float, y: float, seed: int = 0) -> float:
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = _smooth(x - xi), _smooth(y - yi)
    a, b = hash01(xi, yi, seed), hash01(xi + 1, yi, seed)
    c, d = hash01(xi, yi + 1, seed), hash01(xi + 1, yi + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def fbm(x: float, y: float = 0.0, seed: int = 0, octaves: int = 4) -> float:
    """Fractal noise in [0, 1]."""
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * noise2(x * (1 << o), y * (1 << o), seed + o)
        norm += amp
        amp *= 0.5
    return total / norm


# --- font --------------------------------------------------------------------------
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
    ",": "00000 00000 00000 00000 01100 00100 01000",
    ":": "00000 01100 01100 00000 01100 01100 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000",
    "%": "11000 11001 00010 00100 01000 10011 00011",
    ">": "01000 00100 00010 00001 00010 00100 01000",
    "_": "00000 00000 00000 00000 00000 00000 11111",
}
_GLYPHS = {ch: rows.split() for ch, rows in _FONT.items()}
GLYPH_W, GLYPH_H, ADVANCE = 5, 7, 6


def text_width(text: str, size: int = 1) -> int:
    return max(0, len(text) * ADVANCE - 1) * size


# --- canvas ------------------------------------------------------------------------
class Canvas:
    def __init__(self, w: int, h: int, fill: int = INK):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]

    def set(self, x: int, y: int, colour: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = colour

    def text(self, s: str, x: int, y: int, colour: int, size: int = 1,
             shadow: int | None = None, outline: int | None = None) -> None:
        """Draw `s` with its top-left corner at (x, y). Unknown characters are blank.

        `shadow` drops a copy down-right; `outline` rings every pixel, which
        keeps small text readable on any sky.
        """
        if shadow is not None:
            self.text(s, x + size, y + size, shadow, size)
        if outline is not None:
            for dx in (-1, 0, 1):  # always one pixel wide, whatever the text size
                for dy in (-1, 0, 1):
                    if dx or dy:
                        self.text(s, x + dx, y + dy, outline, size)
        for i, ch in enumerate(s.upper()):
            for r, bits in enumerate(_GLYPHS.get(ch, _GLYPHS[" "])):
                for c, bit in enumerate(bits):
                    if bit == "1":
                        for dy in range(size):
                            for dx in range(size):
                                self.set(x + (i * ADVANCE + c) * size + dx, y + r * size + dy, colour)

    def copy(self) -> "Canvas":
        c = Canvas(self.w, self.h)
        c.px = [row[:] for row in self.px]
        return c


def _chunk(kind: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + kind + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))


def _pixels(rows: list[list[int]], scale: int) -> bytes:
    """zlib-compressed scanlines, nearest-neighbour upscaled so the pixels stay hard."""
    raw = bytearray()
    for row in rows:
        raw += (b"\x00" + bytes(v for v in row for _ in range(scale))) * scale
    return zlib.compress(bytes(raw), 9)


def _changed(a: Canvas, b: Canvas) -> tuple[int, int, int, int]:
    """Bounding box (x0, y0, x1, y1), exclusive, of the pixels that differ; 1x1 if none do."""
    ys = [y for y in range(a.h) if a.px[y] != b.px[y]]
    if not ys:
        return 0, 0, 1, 1
    xs = [x for y in ys for x in range(a.w) if a.px[y][x] != b.px[y][x]]
    return min(xs), ys[0], max(xs) + 1, ys[-1] + 1


def apng(frames: list[Canvas], delay_ms: int | list[int] = 200, scale: int = SCALE,
         plays: int = 0) -> bytes:
    """Indexed-colour animated PNG. Frames after the first store only the rectangle that changed.

    Viewers without APNG support show the first frame, so it has to stand on
    its own. `delay_ms` is one delay for every frame or a list with one per
    frame. `plays` = 0 loops forever; otherwise the animation stops on its last frame.
    """
    first = frames[0]
    out = [b"\x89PNG\r\n\x1a\n",
           _chunk(b"IHDR", struct.pack(">IIBBBBB", first.w * scale, first.h * scale, 8, 3, 0, 0, 0))]
    if len(frames) > 1:
        out.append(_chunk(b"acTL", struct.pack(">II", len(frames), plays)))
    out.append(_chunk(b"PLTE", b"".join(bytes(c) for c in PALETTE)))

    seq = 0
    for i, frame in enumerate(frames):
        x0, y0, x1, y1 = (0, 0, frame.w, frame.h) if i == 0 else _changed(frames[i - 1], frame)
        data = _pixels([row[x0:x1] for row in frame.px[y0:y1]], scale)
        if len(frames) > 1:
            out.append(_chunk(b"fcTL", struct.pack(
                ">IIIIIHHBB", seq, (x1 - x0) * scale, (y1 - y0) * scale, x0 * scale, y0 * scale,
                delay_ms if isinstance(delay_ms, int) else delay_ms[i], 1000, 0, 0)))  # dispose: none, blend: source
            seq += 1
        if i == 0:
            out.append(_chunk(b"IDAT", data))
        else:
            out.append(_chunk(b"fdAT", struct.pack(">I", seq) + data))
            seq += 1
    out.append(_chunk(b"IEND", b""))
    return b"".join(out)
