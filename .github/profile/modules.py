"""Project modules: every project in profile.json drawn as a synth module.

All modules share one faceplate so they read as a product family when the
README tiles them two per row. Only the accent colour (cycled through
theme.ACCENTS) and the knob positions (seeded from the slug) differ, so a
module changes only when its content does.

Faceplate, top to bottom: silkscreened kind and status LED, the name in the
dot-matrix face, an OLED with the tagline beside a patched IN/OUT pair, and
one knob per tag. The knobs are decoration, not a skill meter: every pointer
sits within 54 degrees of 12 o'clock, and the LED ring stays dark apart from
one dot that fades in and out beside one knob, like a slow LFO patched in.

The SVG sees its own rendered width, so media queries swap the type for the
size the README gives it:
  * over 300 px (desktop, two per row): the full faceplate at 12-13 units;
  * 201-300 px (tablets, half-screen windows next to GitHub's sidebar): the
    same content with the header, tagline and tag labels redrawn larger, and
    the tick skirts and IN/OUT labels dropped;
  * 200 px and under (phones): only the name, and the kind on the screen.

Animation: status LED pulse (running only, 2.8 s), cable dash flow (2.2 s),
cursor dim-blink (1.6 s), a scan band down the screen (9 s) and the ring LED
(7 s). Each module gets its own phase. The un-animated state is complete.
None of it loops forever: an <img> with any running animation is re-rasterised
every frame, so each loop runs a whole number of cycles, ends within a few
seconds of SETTLE_MS after load and leaves the module on its un-animated state.
"""

from __future__ import annotations

import math
import re
import unicodedata

import dotmatrix
from theme import (ACCENTS, AMBER, CYAN, EDGE, FAINT, GREEN, GRID, MONO_ADVANCE,
                   PURPLE, TEXT, esc, fmt, glow_filter, label, led, panel,
                   panel_gradient, rng, scanlines_pattern, svg_doc, text_width, wrap)

W, H = 440, 268
LEFT, RIGHT = 32, 408            # content margins, clear of the corner screws
HEAD_Y = 22                      # header baseline, level with the top screws
# Rendered widths (px) where the type changes. Below MID_MAX 12-unit labels
# would drop under ~8 px, so the mid tier redraws them at MID_SIZE; below
# COMPACT_MAX even that is too small and only the kind is left.
MID_MAX, COMPACT_MAX = 300, 200
MID_SIZE = 16                    # header and tag labels in the mid tier
MID_HEAD_Y = 23.5                # puts 16-unit caps level with the status LED

# DIM measures 4.2:1 on this faceplate; silkscreen needs a touch more light for AA
SILK = "#9A8CC4"

NAME_TOP = 38
NAME_PITCH = (2.6, 4.4)          # dot pitch range for the name

SCR_X, SCR_Y, SCR_W, SCR_H = LEFT, 80, 262, 70
SCR_SIZE, SCR_LH, SCR_PAD = 13, 17, 13
SCR_LINES = 3
MID_SCR = (18, 20, 3)            # screen type size, line height, lines in the mid tier
CMP_SCR = (26, 30, 2)            # ... and in the compact tier

JACK_Y = 120
JACK_IN, JACK_OUT = 334, 392

KNOB_Y = 196
KNOB_R = 15
RING_R = 20.5
SWEEP = 135                      # knob travel either side of 12 o'clock
DETENTS = 10                     # 11 ticks and 11 ring LEDs across the sweep
# Pointers only use the middle detents (-54..+54 degrees). A knob turned right
# down or right up next to a tag name would read as a rating of that tag.
KNOB_BAND = range(3, 8)
MAX_KNOBS = 4

STATUS_COLORS = {"running": GREEN, "public": CYAN, "stable": PURPLE}

# Ambient loops run for about this long after load, then the module rests.
SETTLE_MS = 45000

# letters the 5x7 font lacks and NFKD cannot take apart
_LIGATURES = str.maketrans({"Æ": "AE", "æ": "ae", "Ø": "O", "ø": "o", "Œ": "OE",
                            "œ": "oe", "ß": "ss", "Ł": "L", "ł": "l", "&": "+"})


# --- small helpers -------------------------------------------------------------
def _label_w(text: str, size: float, spacing: float) -> float:
    """Worst-case width of a silkscreen label including its letter-spacing."""
    return text_width(text, size) + spacing * len(text)


def _polar(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    """Point on a circle, 0 degrees at 12 o'clock, clockwise positive."""
    a = math.radians(deg)
    return cx + r * math.sin(a), cy - r * math.cos(a)


def _detent_angle(pos: int) -> float:
    return -SWEEP + pos * (2 * SWEEP / DETENTS)


def matrix_text(text: str) -> str:
    """Fold accents (a Swedish name would otherwise lose its vowels) so the
    5x7 font, which only has plain A-Z, can draw it."""
    folded = unicodedata.normalize("NFKD", str(text).translate(_LIGATURES))
    return "".join(c for c in folded if not unicodedata.combining(c))


def slug_of(project: dict) -> str:
    raw = project.get("slug") or project.get("name") or "project"
    return re.sub(r"[^a-z0-9]+", "-", matrix_text(raw).lower()).strip("-") or "project"


def tint(color: str, amount: float) -> str:
    """Mix a #RRGGBB colour toward white; OLED text needs more light than purple has."""
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(c + (255 - c) * amount):02X}" for c in rgb)


def tinted_glow(fid: str, color: str, std: float, opacity: float) -> str:
    """Bloom in a fixed colour, so near-white dots get an accent-coloured halo."""
    return (
        f"<filter id='{fid}' x='-20%' y='-60%' width='140%' height='220%' "
        f"color-interpolation-filters='sRGB'>"
        f"<feGaussianBlur in='SourceAlpha' stdDeviation='{fmt(std)}' result='b'/>"
        f"<feFlood flood-color='{color}' flood-opacity='{fmt(opacity)}'/>"
        f"<feComposite in2='b' operator='in' result='g'/>"
        f"<feMerge><feMergeNode in='g'/><feMergeNode in='SourceGraphic'/></feMerge>"
        f"</filter>"
    )


def name_pitch(projects: list[dict]) -> float:
    """One dot pitch for every module, set by the longest name, so the family
    shares a single type size."""
    widest = max((dotmatrix.measure(matrix_text(str(p.get("name", "")))) for p in projects),
                 default=1)
    lo, hi = NAME_PITCH
    return max(lo, min(hi, (RIGHT - LEFT) / max(widest, 1)))


def fit_lines(text: str, cols: int, max_lines: int) -> list[str]:
    """Wrap to `cols`, hyphenating words too long for a line (Swedish
    compounds get long), and end with '...' if it runs past `max_lines`."""
    words = []
    for word in str(text).split():
        while len(word) > cols:
            words.append(word[:cols - 1] + "-")
            word = word[cols - 1:]
        words.append(word)
    lines = wrap(" ".join(words), cols) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if len(last) > cols - 3:
            cut = last[:cols - 3]
            # end on a whole word unless the cut already fell between two
            if last[cols - 3] != " " and " " in cut:
                cut = cut.rsplit(" ", 1)[0]
            last = cut
        lines[-1] = last.rstrip(" ,;:-") + "..."
    return lines


def fit_kind(kind: str, size: float, room: float) -> tuple[str, float]:
    """The kind in the header: letter-spacing closes up a step at a time
    before any word is dropped, so it stays close to its siblings."""
    txt = kind.upper()
    steps = [s * size / 12 for s in (2.6, 2.0, 1.4, 1.0)]
    if _label_w(txt, size, steps[-1]) > room:
        n = len(txt)
        while n and _label_w(txt[:n], size, steps[-1]) > room:
            n -= 1
        cut = txt[:n]
        # drop the partial word, unless the cut fell on a space anyway; a lone
        # word that cannot fit is abbreviated the way the knob labels are
        if n < len(txt) and txt[n] != " ":
            if " " in cut:
                cut = cut.rsplit(" ", 1)[0]
            elif len(cut) > 2:
                cut = cut[:-1] + "."
        txt = cut.rstrip()
    spacing = next((s for s in steps if _label_w(txt, size, s) <= room), steps[-1])
    return txt, spacing


# --- faceplate sections --------------------------------------------------------
def status_led(status: str) -> str:
    st = status.lower()
    return led(RIGHT - 4, HEAD_Y - 4.3, STATUS_COLORS.get(st, AMBER), r=3.4,
               cls="pulse" if st == "running" else "")


def header_text(kind: str, status: str, url: str | None, accent: str,
                size: float, base: float) -> str:
    """Silkscreen row beside the status LED: kind, hairline rule, REPO chip and
    status word. Spacing and the chip scale with `size`, so the mid tier can
    draw the same row larger."""
    k = size / 12
    cy = base - size * 0.36              # optical middle of the capitals
    parts = []
    # the status word is end-anchored against its LED, so the gap stays tight
    # even when the viewer's font is narrower than budgeted
    st_txt = _abbrev(status.upper(), 12)
    st_end = RIGHT - 4 - 11 * k            # LED centre, then a gap that grows with the type
    parts.append(label(st_end, base, st_txt, size=size, color=TEXT, anchor="end",
                       spacing=1.4 * k))
    rule_x1 = st_end - _label_w(st_txt, size, 1.4 * k) - 12 * k

    if url:
        # the README links the whole image; this chip says a repo is behind it
        bx1 = rule_x1
        bx0 = bx1 - _label_w("REPO", size, 1.2 * k) - 26 * k
        ch = size + 5
        ax = bx1 - 10 * k

        def p(dx: float, dy: float) -> str:
            return f"{fmt(ax + dx * k)} {fmt(cy + dy * k)}"

        parts.append(
            f"<rect x='{fmt(bx0)}' y='{fmt(cy - ch / 2)}' width='{fmt(bx1 - bx0)}' "
            f"height='{fmt(ch)}' rx='3' stroke='{accent}' stroke-opacity='.7'/>"
            + label(bx0 + 7 * k, base, "REPO", size=size, color=accent, spacing=1.2 * k)
            + f"<path d='M{p(-3.5, 3.5)}L{p(3, -3)}M{p(-2, -3)}H{fmt(ax + 3 * k)}V{fmt(cy + 2 * k)}' "
              f"stroke='{accent}' stroke-width='{fmt(1.5 * k)}' stroke-linecap='round' "
              f"stroke-linejoin='round'/>"
        )
        rule_x1 = bx0 - 10 * k

    kind_txt, spacing = fit_kind(kind, size, rule_x1 - LEFT - 4 * k)
    parts.append(label(LEFT, base, kind_txt, size=size, color=SILK, spacing=spacing))

    rule_x0 = LEFT + _label_w(kind_txt, size, spacing) + 8 * k
    if rule_x1 - rule_x0 > 16 * k:
        parts.append(
            f"<path d='M{fmt(rule_x0)} {fmt(cy)}H{fmt(rule_x1)}' "
            f"stroke='{accent}' stroke-opacity='.35'/>"
        )
    return "".join(parts)


def header(kind: str, status: str, url: str | None, accent: str) -> str:
    return (status_led(status)
            + f"<g class='fine'>{header_text(kind, status, url, accent, 12, HEAD_Y)}</g>"
            + f"<g class='mid'>{header_text(kind, status, url, accent, MID_SIZE, MID_HEAD_Y)}</g>")


def name_block(name: str, pitch: float) -> str:
    name = matrix_text(name)
    cols = max(1, dotmatrix.measure(name))
    if cols * pitch > RIGHT - LEFT:
        pitch = (RIGHT - LEFT) / cols
    r = pitch * 0.4
    dots = dotmatrix.render(name, LEFT + r, NAME_TOP + r, pitch, radius=r,
                            lit=TEXT, off=None)
    return f"<g filter='url(#ng)'>{dots}</g>"


def screen_text(text: str, size: float, lh: float, max_lines: int, cls: str) -> str:
    """One layout of the screen: centred lines with a blinking cursor after them."""
    x, y, w, h = SCR_X, SCR_Y, SCR_W, SCR_H
    cols = int((w - 2 * SCR_PAD) / (size * MONO_ADVANCE))
    lines = fit_lines(text, cols, max_lines)
    # the cursor rides on the last line, or starts a new one
    if len(lines[-1]) + 2 > cols and len(lines) < max_lines:
        lines.append("")
    cursor_line = len(lines) - 1 if len(lines[-1]) + 2 <= cols else None

    cap = size * 0.72
    block = (len(lines) - 1) * lh + cap
    base0 = y + (h - block) / 2 + cap
    tx = x + SCR_PAD

    txt = "".join(
        f"<text x='{fmt(tx)}' y='{fmt(base0 + i * lh)}' xml:space='preserve'>{esc(line)}</text>"
        for i, line in enumerate(lines)
    )
    cursor = ""
    if cursor_line is not None:
        # a transparent copy of the line pushes the cursor to the exact spot the
        # viewer's own font puts the end of the text
        pre = lines[cursor_line] + " " if lines[cursor_line] else ""
        cursor = (
            f"<text x='{fmt(tx)}' y='{fmt(base0 + cursor_line * lh)}' xml:space='preserve'>"
            f"<tspan fill-opacity='0'>{esc(pre)}</tspan>"
            f"<tspan class='blink'>&#9608;</tspan></text>"
        )
    return f"<g class='{cls}' font-size='{fmt(size)}'><g filter='url(#sg)'>{txt}</g>{cursor}</g>"


def screen(tagline: str, kind: str, accent: str) -> str:
    x, y, w, h = SCR_X, SCR_Y, SCR_W, SCR_H
    tiers = (
        screen_text(tagline, SCR_SIZE, SCR_LH, SCR_LINES, "full")
        + screen_text(tagline, *MID_SCR, "mid")
        # at phone size a truncated sentence helps nobody; the kind fits whole
        + screen_text((kind or tagline).upper(), *CMP_SCR, "compact")
    )
    return (
        # the lit screen spills a little light onto the panel around its bezel
        f"<ellipse cx='{fmt(x + w / 2)}' cy='{fmt(y + h / 2)}' rx='{fmt(w / 2 + 34)}' "
        f"ry='{fmt(h / 2 + 30)}' fill='url(#sp)'/>"
        # bezel, glass, tint
        f"<rect x='{fmt(x - 4)}' y='{fmt(y - 4)}' width='{fmt(w + 8)}' height='{fmt(h + 8)}' rx='8' "
        f"fill='#07040D' stroke='{EDGE}'/>"
        # light catching the lower lip makes the screen read as recessed
        f"<path d='M{fmt(x + 4)} {fmt(y + h + 4.5)}H{fmt(x + w - 4)}' stroke='#FFFFFF' stroke-opacity='.07'/>"
        f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='4' fill='#020104'/>"
        f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='4' fill='url(#st)'/>"
        # the clip is a backstop: nothing should reach the bezel, but a
        # wider-than-budgeted font must not spill onto the patch bay
        f"<g clip-path='url(#sc)'>"
        f"<rect class='scan' x='{fmt(x)}' y='{fmt(y - 18)}' width='{fmt(w)}' height='18' fill='url(#sb)'/>"
        f"<g fill='{tint(accent, 0.3)}'>{tiers}</g>"
        f"</g>"
        f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='4' fill='url(#sl)'/>"
        f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='4' fill='url(#gs)'/>"
    )


def jack(cx: float, cy: float) -> str:
    """Hex nut and threaded barrel of a 3.5 mm jack, seen head-on."""
    pts = " ".join(
        f"{fmt(cx + 9.5 * math.cos(math.radians(30 + 60 * k)))},"
        f"{fmt(cy + 9.5 * math.sin(math.radians(30 + 60 * k)))}"
        for k in range(6)
    )
    return (
        f"<polygon points='{pts}' fill='#1C1330' stroke='#3A2B5C' stroke-width='1'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='6.4' fill='#0D0818' stroke='#2E2148'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='3.6' fill='#000'/>"
    )


def plug(cx: float, cy: float, accent: str) -> str:
    """A patched jack: knurled grip with the cable's coloured boot in the middle."""
    return (
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='8.4' fill='#1D1530' stroke='#443468'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='7' stroke='#000' stroke-opacity='.5' "
        f"stroke-width='1.6' stroke-dasharray='1 1.2'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='4.6' fill='{accent}'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='4.6' fill='url(#pl)'/>"
    )


def patch_bay(accent: str) -> str:
    xi, xo, y = JACK_IN, JACK_OUT, JACK_Y
    ly = y - 17
    out_w = _label_w("OUT", 12, 1.4) + 8
    # outputs are printed reversed out of a filled box, as on real eurorack panels
    labels = (
        label(xi, ly, "IN", size=12, color=SILK, anchor="middle", spacing=1.4)
        + f"<rect x='{fmt(xo - out_w / 2)}' y='{fmt(ly - 11.5)}' width='{fmt(out_w)}' height='15.5' "
          f"rx='2.5' fill='{SILK}'/>"
        + label(xo + 0.7, ly, "OUT", size=12, color="#0B0714", anchor="middle", spacing=1.4,
                weight=700)
    )
    # signal flows out of OUT and back into IN, so the path runs that way. The
    # handles are uneven so the cable sags toward OUT like it has some weight,
    # instead of hanging in a symmetric horseshoe.
    d = (f"M{fmt(xo)} {fmt(y + 4)}C{fmt(xo + 16)} {fmt(y + 60)} "
         f"{fmt(xi - 12)} {fmt(y + 34)} {fmt(xi)} {fmt(y + 4)}")
    cable = (
        f"<path d='{d}' stroke='#05020A' stroke-width='6.4' stroke-linecap='round' opacity='.85'/>"
        f"<path d='{d}' stroke='{accent}' stroke-width='4' stroke-linecap='round' stroke-opacity='.8'/>"
        f"<path d='{d}' stroke='#FFFFFF' stroke-width='1.2' stroke-linecap='round' "
        f"stroke-dasharray='2 8' stroke-opacity='.55' class='flow'/>"
    )
    return (f"<g class='fine'>{labels}</g>" + jack(xi, y) + jack(xo, y) + cable
            + plug(xi, y, accent) + plug(xo, y, accent))


def ring_led(cx: float, cy: float, pos: int, accent: str, cls: str) -> str:
    """One lit dot of a knob's LED ring, with its halo."""
    x, y = _polar(cx, cy, RING_R, _detent_angle(pos))
    return (
        f"<g class='{cls}'><circle cx='{fmt(x)}' cy='{fmt(y)}' r='4.6' fill='{accent}' opacity='.28'/>"
        f"<circle cx='{fmt(x)}' cy='{fmt(y)}' r='2.1' fill='{tint(accent, 0.25)}'/></g>"
    )


def knob(cx: float, cy: float, pos: int, accent: str, wobble: int | None) -> str:
    """Knob with a tick skirt and a ring of 11 unlit LEDs.

    `wobble` is a detent beside the pointer that glows up and fades again, as
    if a slow modulation source were patched in. Nothing on the ring is lit
    otherwise, so the pointer is the only thing that says where a knob is."""
    angle = _detent_angle(pos)
    ticks, ring = [], []
    for k in range(DETENTS + 1):
        a = _detent_angle(k)
        r0 = 24.2 if k in (0, DETENTS) else 25
        x0, y0 = _polar(cx, cy, r0, a)
        x1, y1 = _polar(cx, cy, 27.4, a)
        ticks.append(f"M{fmt(x0)} {fmt(y0)}L{fmt(x1)} {fmt(y1)}")
        lx, ly = _polar(cx, cy, RING_R, a)
        ring.append(f"<circle cx='{fmt(lx)}' cy='{fmt(ly)}' r='1.6'/>")
    lit = "" if wobble is None else ring_led(cx, cy, wobble, accent, "mq")
    ix0, iy0 = _polar(cx, cy, 4.5, angle)
    ix1, iy1 = _polar(cx, cy, 12.5, angle)
    return (
        f"<path class='fine' d='{''.join(ticks)}' stroke='{FAINT}' stroke-width='1.2' "
        f"stroke-linecap='round'/>"
        f"<g fill='{GRID}' stroke='#2A1D44' stroke-width='.6'>{''.join(ring)}</g>"
        f"{lit}"
        # body
        f"<circle cx='{fmt(cx + 0.8)}' cy='{fmt(cy + 2.2)}' r='{fmt(KNOB_R + 0.5)}' fill='#000' opacity='.55'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='{KNOB_R}' fill='url(#kb)' stroke='#34264F'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='13' stroke='#000' stroke-opacity='.45' "
        f"stroke-width='2.4' stroke-dasharray='1.1 1.45'/>"
        f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='10.2' fill='url(#kc)' stroke='#3D2E60' stroke-width='.8'/>"
        f"<path d='M{fmt(ix0)} {fmt(iy0)}L{fmt(ix1)} {fmt(iy1)}' stroke='{TEXT}' stroke-width='2' "
        f"stroke-linecap='round'/>"
    )


def _abbrev(txt: str, fit: int) -> str:
    """Cut the way hardware abbreviates, with a full stop, so it reads as intended."""
    return txt if len(txt) <= fit else txt[:max(2, fit - 1)] + "."


def knob_label(cx: float, y: float, text: str, width: float, size: float = 12) -> str:
    """Tag name under a knob: spacing tightens, the type drops a size, then it
    breaks at the hyphen or dot nearest the middle, then it is abbreviated."""
    k = size / 12
    small = size - k
    txt = text.upper()
    for s, spacing in ((size, 1.2 * k), (size, 0.4 * k), (small, 0.0)):
        if _label_w(txt, s, spacing) <= width:
            return label(cx, y, txt, size=s, color=SILK, anchor="middle", spacing=spacing)
    fit = max(3, int(width / (small * MONO_ADVANCE)))
    breaks = [i for i, c in enumerate(txt) if c in "-." and 0 < i < len(txt) - 1]
    if breaks:
        cut = min(breaks, key=lambda i: abs(len(txt) / 2 - i))
        rows = [_abbrev(txt[: cut + 1], fit), _abbrev(txt[cut + 1:], fit)]
        return "".join(label(cx, y + dy, row, size=small, color=SILK, anchor="middle", spacing=0)
                       for dy, row in zip((-7 * k, 7 * k), rows))
    return label(cx, y, _abbrev(txt, fit), size=small, color=SILK, anchor="middle", spacing=0)


def knob_positions(r, n: int) -> list[int]:
    """Pointer detents drawn from KNOB_BAND without repeats while the band
    lasts. One pass, so any number of tags terminates."""
    band = list(KNOB_BAND)
    return r.sample(band * (1 + (n - 1) // len(band)), n)


def knob_row(tags: list[str], accent: str, seed: str) -> str:
    tags = [t for t in tags if str(t).strip()][:MAX_KNOBS]
    if not tags:
        return ""
    r = rng(seed)
    positions = knob_positions(r, len(tags))
    mod = r.randrange(len(tags))
    wobble = positions[mod] + r.choice((-1, 1))
    cell = (RIGHT - LEFT) / len(tags)
    knobs, fine, mid = [], [], []
    for k, tag in enumerate(tags):
        cx = LEFT + cell * (k + 0.5)
        knobs.append(knob(cx, KNOB_Y, positions[k], accent, wobble if k == mod else None))
        fine.append(knob_label(cx, KNOB_Y + 44, str(tag), cell - 10))
        # the mid tier has no tick skirts, so its labels can take more of the cell
        mid.append(knob_label(cx, KNOB_Y + 44, str(tag), cell - 8, MID_SIZE))
    return ("".join(knobs) + f"<g class='fine'>{''.join(fine)}</g>"
            + f"<g class='mid'>{''.join(mid)}</g>")


# --- document ------------------------------------------------------------------
def _loop(name: str, dur_ms: int, timing: str, delay_ms: int) -> str:
    """A loop that stops after a whole number of cycles.

    The negative delay is the module's phase, so the last cycle ends at
    n * dur + delay; n is picked to land that nearest SETTLE_MS, which puts
    every loop's end within half a cycle of it (the 9 s scan: 40.5-49.5 s).
    Ending on a cycle boundary means the last frame is the 100% keyframe, and
    each keyframe set below ends where its un-animated state is (LEDs lit,
    cursor solid, scan band and ring LED dark, dashes a whole period on), so
    with no fill mode the element drops back to its static look without a jump.
    """
    n = max(1, math.floor((SETTLE_MS - delay_ms) / dur_ms + 0.5))
    return f"animation:{name} {fmt(dur_ms / 1000)}s {timing} {delay_ms}ms {n};"


def module_css(slug: str) -> str:
    # every module gets its own phase, so six cursors and LEDs never blink in
    # lockstep down the page
    ph = rng(slug + "/phase")
    pulse, flow, blink, scan, mod = (-ph.randrange(0, t) for t in (2800, 2200, 1600, 9000, 7000))
    return (
        # later rules win, so the two queries nest without a gap between them
        ".mid,.compact{display:none;}"
        f"@media (max-width:{MID_MAX}px){{.fine,.full{{display:none;}}.mid{{display:inline;}}}}"
        f"@media (max-width:{COMPACT_MAX}px){{.mid{{display:none;}}.compact{{display:inline;}}}}"
        f".pulse{{{_loop('pulse', 2800, 'ease-in-out', pulse)}}}"
        "@keyframes pulse{50%{opacity:.3;}}"
        # -20 is two whole periods of the 2 8 dash, so the end matches offset 0
        f".flow{{{_loop('flow', 2200, 'linear', flow)}}}"
        "@keyframes flow{to{stroke-dashoffset:-20;}}"
        # the cursor dims rather than vanishing: six hard blinks out of phase
        # would be the loudest thing in the grid
        f".blink{{{_loop('blink', 1600, 'ease-in-out', blink)}}}"
        "@keyframes blink{0%,45%{opacity:1;}50%,95%{opacity:.15;}}"
        # the band ends just below the screen, outside the clip, then hides
        f".scan{{opacity:0;{_loop('scan', 9000, 'linear', scan)}}}"
        f"@keyframes scan{{0%{{opacity:1;transform:translateY(0);}}"
        f"100%{{opacity:1;transform:translateY({SCR_H + 18}px);}}}}"
        # modulation lights the ring LED beside one pointer and ebbs away; it
        # is hidden by default, so a static render shows a plain dark ring
        f".mq{{opacity:0;{_loop('mq', 7000, 'ease-in-out', mod)}}}"
        "@keyframes mq{0%,25%,100%{opacity:0;}50%,75%{opacity:.9;}}"
    )


def module_defs(accent: str) -> str:
    return (
        panel_gradient("pg")
        + scanlines_pattern("sl", gap=3, opacity=0.32)
        + tinted_glow("ng", accent, 2.2, 0.75)
        + glow_filter("sg", std=1.8, strength=0.9)
        + "<radialGradient id='kb' cx='.42' cy='.3' r='.8'>"
          "<stop offset='0' stop-color='#2E2146'/><stop offset='1' stop-color='#100A1C'/></radialGradient>"
        + "<linearGradient id='kc' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#2C1F44'/><stop offset='1' stop-color='#140C22'/></linearGradient>"
        + f"<radialGradient id='st' cx='.35' cy='.4' r='.9'>"
          f"<stop offset='0' stop-color='{accent}' stop-opacity='.10'/>"
          f"<stop offset='1' stop-color='{accent}' stop-opacity='0'/></radialGradient>"
        + f"<linearGradient id='sb' x1='0' y1='0' x2='0' y2='1'>"
          f"<stop offset='0' stop-color='{accent}' stop-opacity='0'/>"
          f"<stop offset='.7' stop-color='{accent}' stop-opacity='.10'/>"
          f"<stop offset='1' stop-color='{accent}' stop-opacity='0'/></linearGradient>"
        + f"<radialGradient id='sp'><stop offset='.55' stop-color='{accent}' stop-opacity='.07'/>"
          f"<stop offset='1' stop-color='{accent}' stop-opacity='0'/></radialGradient>"
        + "<linearGradient id='gs' x1='0' y1='0' x2='.35' y2='1'>"
          "<stop offset='0' stop-color='#FFFFFF' stop-opacity='.07'/>"
          "<stop offset='.45' stop-color='#FFFFFF' stop-opacity='0'/></linearGradient>"
        + "<radialGradient id='pl' cx='.38' cy='.32' r='.75'>"
          "<stop offset='0' stop-color='#FFFFFF' stop-opacity='.35'/>"
          "<stop offset='.55' stop-color='#FFFFFF' stop-opacity='0'/>"
          "<stop offset='1' stop-color='#000' stop-opacity='.35'/></radialGradient>"
        + f"<clipPath id='sc'><rect x='{SCR_X}' y='{SCR_Y}' width='{SCR_W}' height='{SCR_H}' rx='4'/></clipPath>"
    )


def module_svg(project: dict, accent: str, pitch: float) -> str:
    slug = slug_of(project)
    name = str(project.get("name") or slug)
    kind = str(project.get("kind") or "module")
    status = str(project.get("status") or "unknown")
    tagline = str(project.get("tagline") or "")
    tags = [str(t) for t in project.get("tags") or []]
    url = project.get("url")

    body = (
        panel(3, 3, W - 6, H - 6, r=14, gradient_id="pg")
        + header(kind, status, url, accent)
        + name_block(name, pitch)
        + screen(tagline, kind, accent)
        + patch_bay(accent)
        + knob_row(tags, accent, slug)
    )
    title = f"{name}: {kind}"
    bits = [tagline, str(project.get("description", "")).strip(),
            f"Status: {status}."]
    if tags:
        bits.append("Built with " + ", ".join(tags) + ".")
    desc = " ".join(b for b in bits if b)
    return svg_doc(W, H, body, title=title, desc=desc, css=module_css(slug),
                   defs=module_defs(accent))


def render(ctx: dict) -> dict[str, str]:
    projects = ctx["content"].get("projects", [])
    pitch = name_pitch(projects)
    return {
        f"module-{slug_of(p)}.svg": module_svg(p, ACCENTS[i % len(ACCENTS)], pitch)
        for i, p in enumerate(projects)
    }
