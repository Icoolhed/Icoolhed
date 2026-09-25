"""Hero and footer: the top and bottom units of the studio rack.

hero.svg is the head unit: the handle on a dot-matrix display that powers
on in a sweep, a small phosphor scope and the status LEDs from profile.json.
footer.svg is the 1U blank that closes the rack. Every moving part here is
decoration, so nothing carries a scale, a number or a label that would make
it read as data.
"""

from __future__ import annotations

import math

import dotmatrix
from theme import (AMBER, CYAN, DIM, EDGE, GREEN, MAGENTA, PURPLE, RED,
                   TEXT, esc, fmt, label, led, panel,
                   panel_gradient, rng, scanlines_pattern, screw, svg_doc,
                   text_width)

W = 900
HERO_H = 256
FOOT_H = 96
EAR = 40                  # rack ear width, each side
FACE_X0, FACE_X1 = 60, 840  # usable face between the ears

LED_COLORS = {"green": GREEN, "cyan": CYAN, "magenta": MAGENTA,
              "red": RED, "amber": AMBER, "purple": PURPLE}

LED_Y = 212                 # centre line of the LED lenses and the subtitle caps
MODEL = "ICH-01"            # silkscreened model number, shared by both units
GLASS = "#06030D"
OFF_DOT = "#1B1132"
LAMP_DOT = "#452978"        # every lamp during the power-on lamp test

# SMIL ignores prefers-reduced-motion, so each SMIL-driven stroke has a still
# twin that is hidden by default and swapped in when motion is reduced.
REDUCED_SWAP = "@media (prefers-reduced-motion: reduce){.smil{display:none}.still{display:inline}}"

# An SVG in an <img> is re-rasterised on every frame for as long as anything in
# it animates, so nothing loops forever: every loop plays whole cycles until
# REST_BY seconds after load and stops on its last keyframe, which is also its
# un-animated state. From then on both units are still pictures.
REST_BY = 48.0


def loops(dur: float, delay: float = 0.0) -> int:
    """Whole cycles of a loop starting at `delay` that are over by REST_BY (at least one)."""
    return max(1, int((REST_BY - delay) // dur))


def render(ctx: dict) -> dict[str, str]:
    hero = ctx["content"].get("hero", {})
    return {"hero.svg": hero_svg(hero), "footer.svg": footer_svg(hero)}


# --- shared hardware -------------------------------------------------------------
def rack_defs() -> str:
    return (
        panel_gradient("face")
        + "<linearGradient id='bez' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#010003'/><stop offset='.55' stop-color='#0B0616'/>"
          "<stop offset='1' stop-color='#241838'/></linearGradient>"
        + "<linearGradient id='bar' x1='0' y1='0' x2='1' y2='0'>"
          "<stop offset='0' stop-color='#07040D'/><stop offset='.3' stop-color='#3B2A5C'/>"
          "<stop offset='.55' stop-color='#1C1233'/><stop offset='1' stop-color='#060309'/></linearGradient>"
        + "<linearGradient id='shade' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#000' stop-opacity='.65'/>"
          "<stop offset='1' stop-color='#000' stop-opacity='0'/></linearGradient>"
        # the lower half of a lip-spill mask: black fading in towards the bottom
        + "<linearGradient id='lipv' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#000' stop-opacity='0'/><stop offset='1' stop-color='#000'/>"
          "</linearGradient>"
    )


def rack_frame(w: float, h: float, slot_ys: list[float], handles: bool = False) -> str:
    """Full-width panel with a rack ear on each side, slotted for screws."""
    out = [panel(1, 1, w - 2, h - 2, r=7, screws=False, gradient_id="face")]
    for x0 in (1, w - EAR - 1):
        # ears are the same sheet of metal, just a shade darker past the fold
        out.append(f"<rect x='{fmt(x0 + 0.5)}' y='1.5' width='{EAR}' height='{fmt(h - 3)}' "
                   f"rx='6.5' fill='#000' opacity='.22'/>")
    for gx in (EAR + 1, w - EAR - 1):
        out.append(f"<path d='M{gx} 2V{fmt(h - 2)}' stroke='#000' stroke-opacity='.6'/>"
                   f"<path d='M{gx + 1} 2V{fmt(h - 2)}' stroke='#FFF' stroke-opacity='.05'/>")
    for cx in (EAR / 2 + 1, w - EAR / 2 - 1):
        for cy in slot_ys:
            out.append(rack_slot(cx, cy))
        if handles:
            out.append(rack_handle(cx, slot_ys[0] + 26, slot_ys[-1] - 26))
    return "".join(out)


def rack_handle(cx: float, y0: float, y1: float) -> str:
    """Front handle: two mounting blocks and a round bar with a specular line."""
    out = [f"<rect x='{fmt(cx - 4)}' y='{fmt(y0 + 3)}' width='14' height='{fmt(y1 - y0)}' rx='7' "
           f"fill='#000' opacity='.35'/>"]
    for by in (y0, y1):
        out.append(f"<rect x='{fmt(cx - 9)}' y='{fmt(by - 7)}' width='18' height='14' rx='3' "
                   f"fill='#120B20' stroke='#000' stroke-opacity='.7'/>"
                   f"<circle cx='{fmt(cx)}' cy='{fmt(by)}' r='2' fill='#05030A'/>")
    out.append(f"<rect x='{fmt(cx - 6)}' y='{fmt(y0 - 2)}' width='12' height='{fmt(y1 - y0 + 4)}' rx='6' "
               f"fill='url(#bar)' stroke='#000' stroke-opacity='.6'/>"
               f"<path d='M{fmt(cx - 2.2)} {fmt(y0 + 8)}V{fmt(y1 - 8)}' stroke='#FFF' stroke-opacity='.13' "
               f"stroke-width='1.4' stroke-linecap='round'/>")
    return "".join(out)


def rack_slot(cx: float, cy: float) -> str:
    """Oblong mounting slot with a rack screw sitting off-centre in it."""
    return (
        f"<rect x='{fmt(cx - 11)}' y='{fmt(cy - 4.5)}' width='22' height='9' rx='4.5' "
        f"fill='#020106' stroke='#000' stroke-opacity='.8'/>"
        f"<path d='M{fmt(cx - 7)} {fmt(cy + 5)}H{fmt(cx + 7)}' stroke='#FFF' stroke-opacity='.06'/>"
        + screw(cx - 3.5, cy, r=6, angle=35 + cy % 50)
    )


def bezel(x: float, y: float, w: float, h: float, ring: float = 7) -> str:
    """Recessed window: shadowed cut edge, a lip that catches light at the bottom."""
    return (
        f"<rect x='{fmt(x - 0.5)}' y='{fmt(y - 0.5)}' width='{fmt(w + 1)}' height='{fmt(h + 1)}' "
        f"rx='6.5' stroke='#000' stroke-opacity='.8'/>"
        f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='6' fill='url(#bez)'/>"
        f"<path d='M{fmt(x + 6)} {fmt(y + h + 1.5)}H{fmt(x + w - 6)}' stroke='#FFF' stroke-opacity='.07'/>"
        f"<rect x='{fmt(x + ring)}' y='{fmt(y + ring)}' width='{fmt(w - 2 * ring)}' "
        f"height='{fmt(h - 2 * ring)}' rx='2.5' fill='{GLASS}'/>"
    )


def lip_spill(uid: str, x: float, y: float, w: float, h: float, ring: float, fill: str,
              opacity: float, lit: tuple[float, float], cls: str = "") -> tuple[str, str]:
    """Light from the screen falling on the bezel's lower lip.

    It is strongest under the lit part of the screen (`lit` = x0, x1) and right
    at the glass edge, and fades out sideways and down the lip, so it reads as
    light on metal rather than a coloured bar.
    """
    lx, ly, lw, lh = x + ring, y + h - ring + 1, w - 2 * ring, ring - 2.5
    x0, x1 = max(lx, lit[0] - 24), min(lx + lw, lit[1] + 24)
    ramp = min(60.0, (x1 - x0) / 4) / (x1 - x0)
    box = f"x='{fmt(lx)}' y='{fmt(ly)}' width='{fmt(lw)}' height='{fmt(lh)}'"
    # mask = sideways ramp (white) times downward fade (black laid over it)
    defs = (
        f"<linearGradient id='{uid}h' gradientUnits='userSpaceOnUse' x1='{fmt(x0)}' y1='0' x2='{fmt(x1)}' y2='0'>"
        f"<stop offset='0' stop-color='#FFF' stop-opacity='0'/>"
        f"<stop offset='{fmt(ramp, 3)}' stop-color='#FFF'/><stop offset='{fmt(1 - ramp, 3)}' stop-color='#FFF'/>"
        f"<stop offset='1' stop-color='#FFF' stop-opacity='0'/></linearGradient>"
        f"<mask id='{uid}' maskUnits='userSpaceOnUse' {box}>"
        f"<rect {box} fill='url(#{uid}h)'/><rect {box} fill='url(#lipv)'/></mask>"
    )
    # the fade-in class animates opacity, so it goes on a wrapper, not on the rect
    c = f" class='{cls}'" if cls else ""
    body = f"<g{c}><rect {box} rx='2' fill='{fill}' opacity='{fmt(opacity)}' mask='url(#{uid})'/></g>"
    return body, defs


def glass_finish(uid: str, x: float, y: float, w: float, h: float, *, scan: bool = True,
                 sheen: float = 0.055) -> tuple[str, str]:
    """Scanlines, top shadow and a soft reflection over a screen area."""
    body = []
    if scan:
        body.append(f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' fill='url(#scan)'/>")
    body.append(f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='10' fill='url(#shade)'/>")
    if sheen <= 0:
        return "".join(body), ""
    # The sheen fades from the top-left corner along the normal of a diagonal
    # (62% along the top edge to 38% along the bottom) and is gone before it
    # gets there, so no edge of it is ever visible.
    nx, ny = h, 0.24 * w
    n = math.hypot(nx, ny)
    reach = 0.62 * w * h / n
    defs = (
        f"<linearGradient id='{uid}' gradientUnits='userSpaceOnUse' x1='{fmt(x)}' y1='{fmt(y)}' "
        f"x2='{fmt(x + nx / n * reach)}' y2='{fmt(y + ny / n * reach)}'>"
        f"<stop offset='0' stop-color='#FFF' stop-opacity='{fmt(sheen, 3)}'/>"
        f"<stop offset='.45' stop-color='#FFF' stop-opacity='{fmt(sheen * 0.45, 3)}'/>"
        f"<stop offset='.85' stop-color='#FFF' stop-opacity='0'/></linearGradient>"
    )
    body.append(f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='2.5' "
                f"fill='url(#{uid})'/>")
    return "".join(body), defs


def pinned(text: str, size: float, spacing: float) -> tuple[float, str]:
    """Budgeted width of a line of mono text, and attributes that hold it there.

    The budget (theme.text_width plus tracking) is the widest a normal mono
    font gets, but a fallback without a bold face is synthesised wider still
    (Lucida Console at 600 measures about 0.71em). textLength pins the line to
    the budget, so such a font only tightens the tracking instead of running
    into whatever comes next.
    """
    w = text_width(text, size) + len(text) * spacing
    return w, f" textLength='{fmt(w)}' lengthAdjust='spacing'"


def silk_rule(x0: float, x1: float, y: float, text: str, size: float = 8.5) -> str:
    """Section label followed by a hairline, the way panels mark a block."""
    tw, fit = pinned(text.upper(), size, 1.8)
    return (label(x0, y, text, size=size, color=DIM, spacing=1.8, extra=fit)
            + f"<path d='M{fmt(x0 + tw + 8)} {fmt(y - size * 0.35)}H{fmt(x1)}' "
              f"stroke='{EDGE}' stroke-width='1'/>")


def model_badge(x0: float, x1: float, y: float, model: str, name: str) -> str:
    """Model number in bold, product name in silkscreen, hairline to the block edge."""
    mw, fit = pinned(model.upper(), 11, 2)
    return (label(x0, y, model, size=11, color=TEXT, weight=700, spacing=2, extra=fit)
            + silk_rule(x0 + mw + 8, x1, y, name))


# --- hero ------------------------------------------------------------------------
def hero_svg(hero: dict) -> str:
    handle = str(hero.get("handle", "ICOOLHED")).upper()
    subtitle = str(hero.get("subtitle", ""))
    leds = hero.get("leds", [])

    disp = (FACE_X0, 50, 554, 136)
    scope_box = (630, 50, FACE_X1 - 630, 136)

    display_body, display_defs = matrix_display(handle, *disp)
    scope_body, scope_defs = scope(*scope_box)

    body = [
        rack_frame(W, HERO_H, [34, HERO_H - 34], handles=True),
        model_badge(FACE_X0, disp[0] + disp[2], 35, MODEL, "dot matrix ident"),
        silk_rule(scope_box[0], FACE_X1, 35, "scope"),
        display_body,
        scope_body,
        # subtitle caps and LED lenses share one centre line
        subtitle_line(subtitle, FACE_X0, LED_Y, disp[2]),
        led_row(leds, scope_box[0], FACE_X1, LED_Y),
    ]
    defs = (rack_defs() + display_defs + scope_defs
            + scanlines_pattern("scan", gap=3, opacity=0.22))
    title = f"{handle}: {' '.join(subtitle.split())}" if subtitle else handle
    desc = (f"A neon rack-mount panel. A dot-matrix display lights up the name {handle} "
            f"in a sweep, next to a small oscilloscope and status LEDs"
            + (" labelled " + ", ".join(str(item.get("label", "")) for item in leds) if leds else "")
            + ".")
    return svg_doc(W, HERO_H, "".join(body), title=title, desc=desc,
                   css=HERO_CSS + drift_css() + beam_css() + REDUCED_SWAP, defs=defs)


def centre_span(n: int, lo: int, hi: int) -> tuple[int, int]:
    """Grid size and offset that leave equal dark margins around lit span lo..hi.

    Glyph cells are not optically centred (an 'I' leaves its first column
    dark, a 'D' fills its last), so it is the lit dots that get centred. When
    parity makes that impossible the grid loses one line.
    """
    span = hi - lo + 1
    if (n - span) % 2:
        n -= 1
    return n, (n - span) // 2 - lo


GLOW_STD = 3.6


def glow(box: tuple[float, float, float, float]) -> str:
    """Bloom for the lit name, like theme.glow_filter but with a tight region.

    The colour drift changes the filtered pixels on every frame, so the blur
    runs on every frame; the default region (4x the bounding box) would blur
    mostly empty glass. 3 sigma plus a pixel of slack is all the bloom needs.
    """
    m = 3 * GLOW_STD + 1
    x0, y0, x1, y1 = box
    return (
        f"<filter id='glow' filterUnits='userSpaceOnUse' x='{fmt(x0 - m)}' y='{fmt(y0 - m)}' "
        f"width='{fmt(x1 - x0 + 2 * m)}' height='{fmt(y1 - y0 + 2 * m)}' color-interpolation-filters='sRGB'>"
        f"<feGaussianBlur in='SourceGraphic' stdDeviation='{fmt(GLOW_STD)}' result='b'/>"
        f"<feComponentTransfer in='b' result='b2'><feFuncA type='linear' slope='1.5'/></feComponentTransfer>"
        f"<feMerge><feMergeNode in='b2'/><feMergeNode in='SourceGraphic'/></feMerge>"
        f"</filter>"
    )


def matrix_display(handle: str, x: float, y: float, w: float, h: float) -> tuple[str, str]:
    """The handle on a full-field dot matrix, glowing through a scanlined glass."""
    ring, pad = 7, 5
    gx, gy, gw, gh = x + ring, y + ring, w - 2 * ring, h - 2 * ring
    fw, fh = gw - 2 * pad, gh - 2 * pad
    text_cols = dotmatrix.measure(handle)
    glyph = [(c, rw) for c, rw, on in dotmatrix.dots(handle) if on]
    # at least 3 dark columns and 2 dark rows around the text, then fill the glass
    pitch = min(fw / (text_cols + 6), fh / (dotmatrix.ROWS + 4))
    c_lo, c_hi = (min(c for c, _ in glyph), max(c for c, _ in glyph)) if glyph else (0, text_cols - 1)
    r_lo, r_hi = (min(r for _, r in glyph), max(r for _, r in glyph)) if glyph else (0, dotmatrix.ROWS - 1)
    cols, c0 = centre_span(int(fw // pitch), c_lo, c_hi)
    rows, r0 = centre_span(int(fh // pitch), r_lo, r_hi)
    ox = gx + (gw - cols * pitch) / 2 + pitch / 2
    oy = gy + (gh - rows * pitch) / 2 + pitch / 2
    tx, ty = ox + c0 * pitch, oy + r0 * pitch
    r = pitch * 0.38

    cores = "".join(f"M{fmt(tx + c * pitch)} {fmt(ty + rw * pitch)}h0" for c, rw in sorted(glyph))

    jitter = rng("hero-sweep:" + handle)
    span = max(1, text_cols - 1)

    def sweep(col: int, row: int) -> str:
        # left-to-right power-on with a slight diagonal and a little noise
        d = 0.35 + 1.0 * col / span + 0.012 * row + jitter.uniform(0, 0.05)
        return f" style='animation-delay:{d:.2f}s'"

    lit_dots = dotmatrix.render(handle, tx, ty, pitch, radius=r, lit="url(#lit)", off=None,
                                lit_class="px", style_fn=sweep)
    x0, x1 = tx + c_lo * pitch - r, tx + c_hi * pitch + r
    y0, y1 = ty + r_lo * pitch - r, ty + r_hi * pitch + r
    # The unlit field is one pattern-filled rect: every lamp, including the
    # ones under the name, so nothing reads as a stencil before the sweep.
    # A pattern also costs far less to repaint than hundreds of little dots.
    fx, fy = ox - pitch / 2, oy - pitch / 2
    field = f"x='{fmt(fx)}' y='{fmt(fy)}' width='{fmt(cols * pitch)}' height='{fmt(rows * pitch)}'"

    def lamps(pid: str, color: str) -> str:
        return (f"<pattern id='{pid}' patternUnits='userSpaceOnUse' x='{fmt(fx)}' y='{fmt(fy)}' "
                f"width='{fmt(pitch)}' height='{fmt(pitch)}'>"
                f"<circle cx='{fmt(pitch / 2)}' cy='{fmt(pitch / 2)}' r='{fmt(r)}' fill='{color}'/></pattern>")

    defs = (
        f"<linearGradient id='lit' gradientUnits='userSpaceOnUse' x1='{fmt(x0)}' y1='0' x2='{fmt(x1)}' y2='0'>"
        f"<stop class='s1' offset='0' stop-color='{CYAN}'/>"
        f"<stop class='s2' offset='.5' stop-color='{MAGENTA}'/>"
        f"<stop class='s3' offset='1' stop-color='{PURPLE}'/></linearGradient>"
        f"<radialGradient id='backlight' cx='.5' cy='.5' r='.7'>"
        f"<stop offset='0' stop-color='{PURPLE}' stop-opacity='.16'/>"
        f"<stop offset='1' stop-color='{PURPLE}' stop-opacity='0'/></radialGradient>"
        + lamps("off", OFF_DOT) + lamps("hot", LAMP_DOT)
        + glow((x0, y0, x1, y1))
    )
    glass, glass_defs = glass_finish("sheen", gx, gy, gw, gh)
    spill, spill_defs = lip_spill("spill", x, y, w, h, ring, "url(#lit)", 0.4, (x0, x1), cls="core")
    body = (
        bezel(x, y, w, h, ring)
        + f"<rect class='bl' x='{fmt(gx)}' y='{fmt(gy)}' width='{fmt(gw)}' height='{fmt(gh)}' fill='url(#backlight)'/>"
        + f"<rect {field} fill='url(#off)'/>"
        # lamp test: shown only inside its keyframes, so the resting state is dark
        + f"<rect class='lamp' {field} fill='url(#hot)' opacity='0'/>"
        + f"<g filter='url(#glow)'>{lit_dots}</g>"
        + f"<path class='core' d='{cores}' stroke='#FFFFFF' stroke-opacity='.45' "
          f"stroke-width='{fmt(r * 0.9)}' stroke-linecap='round'/>"
        + glass
        + spill
    )
    return body, defs + glass_defs + spill_defs


# --- oscilloscope ----------------------------------------------------------------------
SCOPE_POINTS = 97


def sigma(k: int, m: int) -> float:
    """Lanczos sigma factor: tapers harmonic k of m so plateaus stay flat, not rippled."""
    x = math.pi * k / m
    return math.sin(x) / x


def waveforms() -> list[list[float]]:
    """Decorative shapes the trace morphs through, each normalised to about +-1."""
    def sine(t): return math.sin(2 * math.pi * 2 * t)

    def saw(t):
        # jumps fall at 1/4 and 3/4, so both frame edges are mid-ramp
        return 0.85 * (2 / math.pi) * sum((-1) ** (k + 1) * sigma(k, 12)
                                          * math.sin(2 * math.pi * 2 * k * t) / k
                                          for k in range(1, 12))

    def square(t):
        # an eighth late, so both frame edges sit mid-plateau instead of on a jump
        u = t + 0.125
        return 0.8 * (4 / math.pi) * sum(sigma(k, 16) * math.sin(2 * math.pi * 2 * k * u) / k
                                         for k in range(1, 16, 2))

    def kick(t):
        phase = 2 * math.pi * (1.6 * t + 7 * (1 - math.exp(-5 * t)) / 5)
        return math.exp(-2.4 * t) * math.sin(phase)

    def fm(t): return 0.9 * math.sin(2 * math.pi * 2 * t + 2.2 * math.sin(2 * math.pi * 4 * t))

    n = SCOPE_POINTS - 1
    return [[f(i / n) for i in range(SCOPE_POINTS)] for f in (sine, saw, kick, square, fm)]


def trace_d(ys: list[float], x: float, w: float, cy: float, amp: float) -> str:
    n = len(ys) - 1
    pts = [f"{x + w * i / n:.1f} {cy - amp * v:.1f}" for i, v in enumerate(ys)]
    return "M" + "L".join(pts)


def morph_values(frames: list[str], hold: float, move: float) -> tuple[str, str, str, float]:
    """values/keyTimes/keySplines for a hold-then-ease cycle through `frames`."""
    values, times, splines = [], [], []
    total = len(frames) * (hold + move)
    t = 0.0
    for f in frames:
        values += [f, f]
        times += [t, t + hold]
        t += hold + move
        splines += ["0 0 1 1", ".45 0 .2 1"]
    values.append(frames[0])
    times.append(total)
    kt = ";".join(fmt(v / total, 4) for v in times)
    return ";".join(values), kt, ";".join(splines), total


def scope(x: float, y: float, w: float, h: float) -> tuple[str, str]:
    ring = 7
    gx, gy, gw, gh = x + ring, y + ring, w - 2 * ring, h - 2 * ring
    ix, iy, iw, ih = gx + 5, gy + 5, gw - 10, gh - 10
    nx, ny = 8, 6
    grid = []
    for i in range(1, nx):
        gxl = ix + iw * i / nx
        grid.append(f"M{fmt(gxl)} {fmt(iy)}V{fmt(iy + ih)}")
    for j in range(1, ny):
        gyl = iy + ih * j / ny
        grid.append(f"M{fmt(ix)} {fmt(gyl)}H{fmt(ix + iw)}")
    cx, cy = ix + iw / 2, iy + ih / 2
    ticks = []
    for k in range(1, nx * 5):
        tx = ix + iw * k / (nx * 5)
        ticks.append(f"M{fmt(tx)} {fmt(cy - 1.8)}v3.6")
    for k in range(1, ny * 5):
        ty = iy + ih * k / (ny * 5)
        ticks.append(f"M{fmt(cx - 1.8)} {fmt(ty)}h3.6")

    amp = ih * 0.33
    frames = [trace_d(ys, ix + 1, iw - 2, cy, amp) for ys in waveforms()]
    values, key_times, splines, dur = morph_values(frames, hold=1.7, move=1.1)

    def morph(begin: float) -> str:
        # every cycle ends back on the sine, the plain d, and the last one freezes there
        return (f"<animate attributeName='d' dur='{fmt(dur)}s' begin='{fmt(begin)}s' "
                f"repeatCount='{loops(dur, begin)}' fill='freeze' "
                f"calcMode='spline' values='{values}' keyTimes='{key_times}' keySplines='{splines}'/>")

    def trace(href: str) -> str:
        # phosphor: wide faint bloom, mid glow, hot thin core
        return (f"<use href='#{href}' stroke='{CYAN}' stroke-opacity='.13' stroke-width='6'/>"
                f"<use href='#{href}' stroke='{CYAN}' stroke-opacity='.35' stroke-width='2.6'/>"
                f"<use href='#{href}' stroke='#C8FCFF' stroke-opacity='.85' stroke-width='1.2'/>")

    glass, glass_defs = glass_finish("sheen2", gx, gy, gw, gh, scan=False)
    spill, spill_defs = lip_spill("spill2", x, y, w, h, ring, CYAN, 0.16, (ix, ix + iw), cls="scp")
    defs = (
        f"<radialGradient id='phos' cx='.5' cy='.5' r='.75'>"
        f"<stop offset='0' stop-color='#0A1726'/><stop offset='1' stop-color='{GLASS}'/></radialGradient>"
        # the first morph waits until the trace has faded in (.scp, 1.2s-1.7s)
        # and held its sine a moment; before `begin` the plain d is shown
        f"<path id='tr' pathLength='1000' d='{frames[0]}'>{morph(1.2)}</path>"
        f"<path id='gh' d='{frames[0]}'>{morph(1.55)}</path>"
        f"<path id='tr0' d='{frames[0]}'/>"
        f"<clipPath id='scr'><rect x='{fmt(gx)}' y='{fmt(gy)}' width='{fmt(gw)}' height='{fmt(gh)}' rx='2.5'/></clipPath>"
        + glass_defs + spill_defs
    )
    body = (
        bezel(x, y, w, h, ring)
        + f"<rect class='bl' x='{fmt(gx)}' y='{fmt(gy)}' width='{fmt(gw)}' height='{fmt(gh)}' rx='2.5' fill='url(#phos)'/>"
        + f"<g class='grat'><path d='{''.join(grid)}' stroke='{CYAN}' stroke-opacity='.08' stroke-width='.7'/>"
        + f"<path d='M{fmt(ix)} {fmt(cy)}H{fmt(ix + iw)}M{fmt(cx)} {fmt(iy)}V{fmt(iy + ih)}{''.join(ticks)}' "
          f"stroke='{CYAN}' stroke-opacity='.18' stroke-width='.7'/>"
        + f"<path d='M{fmt(gx + 1)} {fmt(cy - 3.5)}l5 3.5l-5 3.5z' fill='{CYAN}' fill-opacity='.55'/></g>"
        + f"<g class='scp' clip-path='url(#scr)' fill='none' stroke-linejoin='round' stroke-linecap='round'>"
        + f"<g class='smil'><use href='#gh' stroke='{CYAN}' stroke-opacity='.22' stroke-width='1.2'/>"
        + trace("tr")
        + beam("t1", 220, "#C8FCFF", ".16", 2.4)
        + beam("t2", 80, "#FFFFFF", ".32", 2.2)
        + beam("hd", 1, CYAN, ".35", 9)
        + beam("hd", 1, "#FFFFFF", "1", 3.6)
        + "</g>"
        + f"<g class='still' display='none'>{trace('tr0')}</g>"
        + "</g>"
        + glass
        + spill
    )
    return body, defs


BEAM_DUR, BEAM_DELAY = 3.4, 1.4
BEAM_DASHES = (("hd", 1), ("t2", 80), ("t1", 220))  # head dot, short tail, long faint tail
BEAM_PARK = 8  # parked this far before the path start, so no round cap can peek out


def beam(cls: str, length: int, color: str, opacity: str, width: float) -> str:
    """One dash riding the trace (pathLength 1000); all dashes end at the beam head."""
    return (f"<use class='{cls}' href='#tr' stroke='{color}' stroke-opacity='{opacity}' "
            f"stroke-width='{fmt(width)}' stroke-dasharray='{length} 3000' "
            f"stroke-dashoffset='{length + BEAM_PARK}'/>")


def beam_css() -> str:
    # every dash starts parked just before the path and runs until even the
    # longest tail has left it, so each pass, the last one too, ends on an
    # empty screen
    longest = max(length for _, length in BEAM_DASHES)
    passes = loops(BEAM_DUR, BEAM_DELAY)
    out = []
    for cls, length in BEAM_DASHES:
        start, end = length + BEAM_PARK, length - 1 - 1000 - longest
        out.append(f".{cls}{{animation:{cls} {BEAM_DUR}s {BEAM_DELAY}s linear {passes}}}"
                   f"@keyframes {cls}{{0%{{stroke-dashoffset:{start}}}100%{{stroke-dashoffset:{end}}}}}")
    return "".join(out)


# --- silkscreen and LEDs ---------------------------------------------------------------
SUB_MAX, SUB_MIN = 18.0, 8.0          # subtitle font size range
SUB_TRACK_MIN, SUB_TRACK_MAX = 1.0, 2.5


def subtitle_line(subtitle: str, x: float, mid_y: float, max_w: float) -> str:
    """The subtitle as silkscreen, caps centred on `mid_y`; '//' picked out in magenta.

    It is the only descriptive text and the banner shrinks to about a third
    on a phone, so it is set as large as `max_w` allows, then tracked out
    until it spans that width (the display above it) or the tracking gets
    too loose.
    """
    parts = [" ".join(p.split()) for p in subtitle.split("//") if p.strip()]
    if not parts:
        return ""
    sep = " // "
    flat = sep.join(parts).upper()
    n = len(flat)
    size = SUB_MAX
    while size > SUB_MIN and text_width(flat, size) + n * SUB_TRACK_MIN > max_w:
        size -= 0.5
    spacing = min(SUB_TRACK_MAX, max(SUB_TRACK_MIN, (max_w - text_width(flat, size)) / n))
    w, fit = pinned(flat, size, spacing)
    if w > max_w:
        # too long even at the smallest size: squeeze the glyphs rather than
        # run under the LEDs
        fit = f" textLength='{fmt(max_w)}' lengthAdjust='spacingAndGlyphs'"
    baseline = mid_y + 0.36 * size   # half a cap height below the centre line
    spans = f"<tspan fill='{MAGENTA}'>{esc(sep)}</tspan>".join(esc(p.upper()) for p in parts)
    return (f"<text x='{fmt(x)}' y='{fmt(baseline)}' font-size='{fmt(size)}' font-weight='600' fill='{TEXT}' "
            f"letter-spacing='{fmt(spacing)}'{fit} xml:space='preserve'>{spans}</text>")


LED_LABEL_MIN, LED_LABEL_MAX, LED_LABEL_SPACING = 5.5, 8.5, 1.6


def led_row(leds: list[dict], x0: float, x1: float, y: float) -> str:
    """Status LEDs spread evenly under the scope, labels silkscreened below."""
    if not leds:
        return ""
    step = (x1 - x0) / len(leds)
    labels = [str(item.get("label", "")) for item in leds]
    longest = max(len(t) for t in labels) or 1

    def fit(room: float) -> float:
        # font size at which the longest label just fills `room`
        return (room / longest - LED_LABEL_SPACING) / 0.62

    # Too many LEDs or long labels: alternate labels drop to a second line,
    # which doubles the room each one has. Anything still too long is cut.
    stagger = fit(step - 6) < LED_LABEL_MIN and len(leds) > 1
    room = (2 if stagger else 1) * step - 6
    size, max_chars = min(LED_LABEL_MAX, fit(room)), longest
    if size < LED_LABEL_MIN:
        size = LED_LABEL_MIN
        max_chars = max(1, int(room / (size * 0.62 + LED_LABEL_SPACING)))
    out = []
    for i, (item, text) in enumerate(zip(leds, labels)):
        color = LED_COLORS.get(str(item.get("color", "")).lower(), CYAN)
        cx = x0 + step * (i + 0.5)
        on_delay = 0.15 + 0.12 * i
        anim = f"animation:ledon .3s {on_delay:.2f}s both"
        if item.get("blink"):
            # activity light: mostly on with a short soft dip, periods out of step;
            # a cycle ends lit, so the last one leaves it on
            period, start = round(2.8 + 0.9 * (i % 3), 1), round(1.6 + 0.3 * i, 1)
            anim += f",blink {period:.1f}s {start:.1f}s linear {loops(period, start)}"
        ly = y + 20 + (9 if stagger and i % 2 else 0)
        out.append(
            f"<circle cx='{fmt(cx)}' cy='{fmt(y)}' r='5.2' fill='#000' stroke='#000' stroke-opacity='.8'/>"
            f"<circle cx='{fmt(cx)}' cy='{fmt(y)}' r='3.6' fill='{color}' opacity='.22'/>"
            + f"<g style='{anim}'>{led(cx, y, color, r=3.4)}</g>"
            + label(cx, ly, text[:max_chars], size=size, color=DIM, anchor="middle",
                    spacing=LED_LABEL_SPACING)
        )
    return "".join(out)


# Power-on order: LEDs, lamp test, backlight, graticule, sweep, trace, hot cores.
# Everything is hidden only inside keyframes, so without animation the panel is complete.
HERO_CSS = f"""
.px{{animation:px .45s cubic-bezier(.2,.8,.3,1) both;transform-box:fill-box;transform-origin:center}}
@keyframes px{{0%{{opacity:0;transform:scale(.2)}}40%{{opacity:1;transform:scale(1.25)}}100%{{opacity:1;transform:scale(1)}}}}
.bl{{animation:bl .5s ease-out both}}
@keyframes bl{{0%{{opacity:0}}100%{{opacity:1}}}}
.grat{{animation:bl .4s .25s ease-out both}}
.core{{animation:bl .6s 1.75s ease-out both}}
.lamp{{animation:lamp .55s .08s ease-out both}}
@keyframes lamp{{0%,100%{{opacity:0}}25%{{opacity:1}}}}
.scp{{animation:bl .5s 1.2s ease-out both}}
@keyframes drift{{0%,100%{{stop-color:{CYAN}}}33.3%{{stop-color:{PURPLE}}}66.6%{{stop-color:{MAGENTA}}}}}
@keyframes ledon{{0%{{opacity:0}}100%{{opacity:1}}}}
@keyframes blink{{0%,78%{{opacity:1}}80%,96%{{opacity:.12}}98%,100%{{opacity:1}}}}
.still{{display:none}}
"""

DRIFT = 18  # seconds per colour cycle of the lit name


def drift_css() -> str:
    """The name's colours cycling through the three stops, then settling.

    s2 and s3 run two and one thirds of a cycle ahead (negative delays), so
    their counts carry the same fraction: all three stop together, each on
    the keyframe that matches the colour its stop is drawn with.
    """
    n = loops(DRIFT)
    return (f".s1,.s2,.s3{{animation:drift {DRIFT}s linear {n}}}"
            f".s2{{animation-delay:-{DRIFT * 2 // 3}s;animation-iteration-count:{n}.666}}"
            f".s3{{animation-delay:-{DRIFT // 3}s;animation-iteration-count:{n}.333}}")


# --- footer --------------------------------------------------------------------------
FOOT_POINTS = 161
FOOT_PHASES = 12


def trail_frames(x: float, w: float, cy: float, amp: float) -> list[str]:
    """A tone dying away to the right, drawn at evenly spaced phases so it flows."""
    n = FOOT_POINTS - 1
    frames = []
    for k in range(FOOT_PHASES):
        phi = 2 * math.pi * k / FOOT_PHASES
        pts = []
        for i in range(FOOT_POINTS):
            u = i / n
            # soft attack so the tone swells out of the hot spot instead of kinking
            env = math.exp(-3.4 * u) * (1 - math.exp(-u / 0.022))
            v = env * math.sin(2 * math.pi * 11 * u - phi)
            pts.append(f"{x + w * u:.1f} {cy - amp * v:.1f}")
        frames.append("M" + "L".join(pts))
    return frames


def footer_svg(hero: dict) -> str:
    handle = str(hero.get("handle", "ICOOLHED")).upper()
    win = (FACE_X0, 24, 554, 48)
    ring = 6
    gx, gy, gw, gh = win[0] + ring, win[1] + ring, win[2] - 2 * ring, win[3] - 2 * ring
    frames = trail_frames(gx + 10, gw - 20, gy + gh / 2, gh * 0.36)
    values = ";".join(frames + [frames[0]])
    flow = 2.6
    # each cycle ends on the plain d, and the last one freezes there
    wave = (f"<path id='trail' d='{frames[0]}'>"
            f"<animate attributeName='d' dur='{fmt(flow)}s' repeatCount='{loops(flow)}' fill='freeze' "
            f"values='{values}'/></path>"
            f"<path id='trail0' d='{frames[0]}'/>")
    # the window is too short for a visible wedge, so its sheen is only a hint
    glass, glass_defs = glass_finish("sheen", gx, gy, gw, gh, sheen=0.025)
    defs = (
        rack_defs()
        + f"<linearGradient id='fade' gradientUnits='userSpaceOnUse' x1='{fmt(gx)}' y1='0' x2='{fmt(gx + gw)}' y2='0'>"
          f"<stop offset='0' stop-color='{CYAN}'/><stop offset='.45' stop-color='{MAGENTA}' stop-opacity='.8'/>"
          f"<stop offset='1' stop-color='{PURPLE}' stop-opacity='0'/></linearGradient>"
        + wave
        + glass_defs
        + scanlines_pattern("scan", gap=3, opacity=0.22)
    )
    cy = FOOT_H / 2
    ox, oy = gx + 10, gy + gh / 2
    lx = 640

    def tone(href: str) -> str:
        return (f"<use href='#{href}' stroke-width='5' stroke-opacity='.18'/>"
                f"<use href='#{href}' stroke-width='1.4'/>")

    body = [
        rack_frame(W, FOOT_H, [cy]),
        bezel(*win, ring=ring),
        f"<g fill='none' stroke='url(#fade)' stroke-linejoin='round'>"
        f"<g class='smil'>{tone('trail')}</g><g class='still' display='none'>{tone('trail0')}</g></g>",
        # where the tone starts: a small hot spot the trail flows out of
        f"<circle cx='{fmt(ox)}' cy='{fmt(oy)}' r='7' fill='{CYAN}' opacity='.16'/>"
        f"<circle cx='{fmt(ox)}' cy='{fmt(oy)}' r='2.2' fill='#DFFFFF'/>",
        glass,
        f"<circle cx='{lx}' cy='{fmt(cy)}' r='5.2' fill='#000'/>",
        f"<circle cx='{lx}' cy='{fmt(cy)}' r='3.4' fill='{PURPLE}' opacity='.22'/>",
        led(lx, cy, PURPLE, r=3.2, cls="breathe"),
        label(lx + 16, cy - 1, "end of rack", size=10.5, color=TEXT, spacing=2.2),
        label(lx + 16, cy + 13, f"{MODEL} / 1U", size=7.5, color=DIM, spacing=1.8),
        vents(776, FACE_X1, cy, 30),
    ]
    breath = 4.5
    css = (f".breathe{{animation:breathe {fmt(breath)}s ease-in-out {loops(breath)}}}"
           "@keyframes breathe{0%,100%{opacity:1}50%{opacity:.3}}"
           ".still{display:none}" + REDUCED_SWAP)
    return svg_doc(W, FOOT_H, "".join(body), title=f"{handle}: end of rack",
                   desc="The closing 1U rack panel: a tone fading out in a small window, "
                        "a single breathing LED and ventilation slots.",
                   css=css, defs=defs)


def vents(x0: float, x1: float, cy: float, h: float, pitch: float = 8) -> str:
    """Row of punched ventilation slots, dark inside with a lit lower lip."""
    n = int((x1 - x0) // pitch) + 1
    slots, lips = [], []
    for i in range(n):
        x = x1 - i * pitch - 3.4
        slots.append(f"<rect x='{fmt(x)}' y='{fmt(cy - h / 2)}' width='3.4' height='{fmt(h)}' rx='1.7'/>")
        lips.append(f"M{fmt(x + 0.8)} {fmt(cy + h / 2 + 1)}h1.8")
    return (f"<g fill='#030107' stroke='#000' stroke-opacity='.7'>{''.join(slots)}</g>"
            f"<path d='{''.join(lips)}' stroke='#FFF' stroke-opacity='.06'/>")
