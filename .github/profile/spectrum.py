"""Contribution spectrum: the last 12 months as a graphic-EQ style LED analyzer.

One band per week (Sunday-start, like GitHub's own graph). Each band is a
stack of LED segments lit up to the week's total on a square-root scale, so a
quiet week still shows while a busy one does not flatten the rest. Below the
window sit month marks and four dot-matrix readouts, all computed from the
calendar by github_data.summarize(). Without data the panel shows NO SIGNAL
and no numbers at all.

The chassis follows the terminal unit (rack ears, model code, LED group on
the right), so the two read as parts of the same rack.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import dotmatrix
from github_data import summarize
from theme import (BG, CYAN, DIM, EDGE, FAINT, GREEN, MAGENTA, PURPLE, RED, TEXT,
                   fmt, glow_filter, label, led, panel_gradient, screw, svg_doc)

W, H = 900, 302
MODEL = "SPA-03"                    # third unit in the rack, after ICH-01 and TTY-02
EAR = 40                            # rack ear width, as on the terminal unit
EDGE_X = EAR + 10                   # content edge: window bezel and readouts line up here
SLOTS = 53                          # GitHub's calendar is 53 week columns
ROWS = 16                           # LED segments per band
SEG = 7.5                           # segment pitch
SEG_GAP = 2.5
SCREEN = (EDGE_X + 4.0, 48.0, W - 2 * (EDGE_X + 4.0), 148.0)  # x, y, w, h of the display window
MX0, MX1 = SCREEN[0] + 16, SCREEN[0] + SCREEN[2] - 16          # band area inside the window
FLOOR = SCREEN[1] + 137             # bottom edge of the lowest segment row
AXIS_Y = SCREEN[1] + SCREEN[3] + 6  # top of the month ticks
GROOVE_Y = 228.0                    # engraved line between the axis and the readouts
READOUT_Y, READOUT_H = 250.0, 36.0  # readout windows
HEAD_Y, LED_Y = 29.0, 25.5          # header text baseline and LED centre
SWEEP = SCREEN[2] + 120             # travel of the scan line, off-screen to off-screen
INTRO_T0, INTRO_DUR = 0.3, 1.8      # the first pass; bars rise as it crosses them
STEP_S = 0.06                       # seconds per LED segment while a bar rises
HOP = 7                             # peak cap bounce, stays below the glass lip
SWEEP_T0, SWEEP_DUR = 3.6, 10.0     # the ambient passes that follow the intro
SWEEPS = 3                          # loop count; the panel goes idle after ~34 s
IDLE_S = SWEEP_T0 + SWEEPS * SWEEP_DUR           # 33.6 s: the last animation ends here
BLINK_S = 1.6                                    # NO SIGNAL status LED period
BLINKS = math.ceil(round(IDLE_S / BLINK_S, 6))   # 21: the LED stops on the same beat, lit
TOP = FLOOR - ROWS * SEG
PITCH = (MX1 - MX0) / SLOTS
BAR_W = round(PITCH * 0.72, 1)

MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
CAPTION = "contributions / last 12 months / one bar per week"
OFF_DOT = "#2A1D44"                 # unlit readout dot: faint, but every character cell shows

# Every animation is finite and over by IDLE_S. An <img> SVG with any animation
# still running is re-rastered every frame, so after that the panel must be a
# still picture: the same one prefers-reduced-motion shows from the start.
# Fill mode is only ever "backwards": every element's resting state already is
# its final frame, and a finished "forwards" fill keeps Chrome re-rastering.
CSS = f"""
.b{{transform-box:fill-box;transform-origin:50% 100%;animation-name:rise;animation-fill-mode:backwards}}
.h{{animation:hop .8s backwards}}
.f{{animation:hide 0s backwards}}
.i{{animation:intro {INTRO_DUR}s linear {INTRO_T0}s backwards}}
.s{{animation:sweep {SWEEP_DUR:g}s linear {SWEEP_T0:g}s {SWEEPS}}}
.blink{{animation:blink {BLINK_S:g}s steps(2,jump-none) {BLINKS}}}
.nosig{{animation:fade 2.4s ease-in-out 4 alternate}}
.on{{animation:on .9s linear .15s backwards}}
@keyframes rise{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
@keyframes hide{{from,to{{opacity:0}}}}
@keyframes hop{{
  0%{{transform:translateY(0);animation-timing-function:cubic-bezier(.2,.7,.4,1)}}
  40%{{transform:translateY(-{HOP}px);animation-timing-function:cubic-bezier(.55,0,.8,.45)}}
  100%{{transform:translateY(0)}}}}
@keyframes intro{{from{{transform:translateX(0)}}to{{transform:translateX({fmt(SWEEP)}px)}}}}
@keyframes sweep{{0%{{transform:translateX(0)}}70%,100%{{transform:translateX({fmt(SWEEP)}px)}}}}
@keyframes blink{{0%{{opacity:1}}100%{{opacity:.25}}}}
@keyframes fade{{from{{opacity:1}}to{{opacity:.55}}}}
@keyframes on{{0%{{opacity:0}}12%{{opacity:.9}}20%{{opacity:.15}}34%{{opacity:1}}44%{{opacity:.5}}60%,100%{{opacity:1}}}}
"""


# --- colour ---------------------------------------------------------------------
def _rgb(hex_: str) -> tuple[int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))


def _mix(a: str, b: str, t: float) -> str:
    ca, cb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


# Small print that has to be read. DIM alone is just under 4.5:1 on the face.
SILK = _mix(DIM, TEXT, .3)


def ramp(row: int) -> str:
    """Segment colour by height: cyan at the floor, purple mid, magenta on top."""
    t = row / (ROWS - 1)
    return _mix(CYAN, PURPLE, t * 2) if t < 0.5 else _mix(PURPLE, MAGENTA, t * 2 - 1)


def _label_w(text: str, size: float, spacing: float) -> float:
    """Worst-case width of a silkscreen label, letter-spacing included."""
    return len(text) * (size * 0.62 + spacing)


# --- data -> geometry -------------------------------------------------------------
def levels(weeks: list[dict]) -> list[int]:
    """Lit segments per week: sqrt scale against the busiest week, zero stays zero."""
    peak = max((w["count"] for w in weeks), default=0)
    if peak <= 0:
        return [0] * len(weeks)
    return [0 if w["count"] <= 0 else max(1, round(math.sqrt(w["count"] / peak) * ROWS))
            for w in weeks]


def slot_x(slot: int) -> float:
    return MX0 + slot * PITCH + (PITCH - BAR_W) / 2


def month_marks(weeks: list[dict], first_slot: int) -> list[tuple[float, str, bool]]:
    """(x, label, is_january) for every week column that contains a 1st.

    January is printed as its year, so the one bright mark on the axis says
    where the year turns instead of looking like the current month.
    """
    marks = []
    for i, w in enumerate(weeks):
        start = date.fromisoformat(w["start_date"])
        for d in range(7):
            day = start + timedelta(days=d)
            if day.day == 1:
                jan = day.month == 1
                name = str(day.year) if jan else MONTHS[day.month - 1]
                marks.append((slot_x(first_slot + i), name, jan))
    return marks


# --- parts ---------------------------------------------------------------------------
def defs(lv: list[int]) -> str:
    """Shared shapes. #col is a full band; #kN is its lowest N segments (one
    per bar height in use), built from the same rects so nothing is drawn twice."""
    col, colw = [], []
    for r in range(ROWS):
        y = fmt(FLOOR - (r + 1) * SEG + SEG_GAP / 2)
        h = fmt(SEG - SEG_GAP)
        col.append(f"<rect id='s{r}' y='{y}' width='{fmt(BAR_W)}' height='{h}' rx='1' fill='{ramp(r)}'/>")
        colw.append(f"<rect y='{y}' width='{fmt(BAR_W)}' height='{h}' rx='1'/>")
    stacks = [f"<g id='k{n}'>{''.join(_ref(f's{r}') for r in range(n))}</g>"
              for n in sorted(set(lv)) if n > 0]
    sx, sy, sw, sh = SCREEN
    return "".join([
        panel_gradient("pg"),
        glow_filter("gl", std=2.6, strength=0.85),
        glow_filter("gs", std=1.6, strength=0.9),
        f"<g id='col'>{''.join(col)}</g>",
        f"<g id='colw'>{''.join(colw)}</g>",
        *stacks,
        # recessed lip: shadowed along the top edge, catching light along the bottom
        "<linearGradient id='lip' x1='0' y1='0' x2='0' y2='1'>"
        "<stop offset='0' stop-color='#000'/><stop offset='1' stop-color='#3A2860'/></linearGradient>",
        # window glass: darker under the top lip (ending above the top LED
        # row, so the tallest peaks stay bright), faint sheen across the upper half
        "<linearGradient id='glass' x1='0' y1='0' x2='0' y2='1'>"
        "<stop offset='0' stop-color='#000' stop-opacity='.55'/>"
        "<stop offset='.1' stop-color='#000' stop-opacity='0'/></linearGradient>",
        "<linearGradient id='sheen' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#fff' stop-opacity='.05'/>"
        "<stop offset='.5' stop-color='#fff' stop-opacity='0'/></linearGradient>",
        f"<linearGradient id='scan' x1='0' y1='0' x2='1' y2='0'>"
        f"<stop offset='0' stop-color='{CYAN}' stop-opacity='0'/>"
        f"<stop offset='1' stop-color='{CYAN}' stop-opacity='.26'/></linearGradient>",
        f"<clipPath id='scr'><rect x='{fmt(sx)}' y='{fmt(sy)}' width='{fmt(sw)}' height='{fmt(sh)}' rx='6'/></clipPath>",
        f"<mask id='segs' maskUnits='userSpaceOnUse' x='{fmt(sx)}' y='{fmt(sy)}' width='{fmt(sw)}' height='{fmt(sh)}'>"
        f"<g fill='#fff'>{''.join(_use('colw', s) for s in range(SLOTS))}</g></mask>",
    ])


def _ref(ref: str) -> str:
    return f"<use href='#{ref}'/>"


def _use(ref: str, slot: int, extra: str = "") -> str:
    return f"<use href='#{ref}' x='{fmt(slot_x(slot))}'{extra}/>"


def chassis() -> str:
    """Panel face with rack ears and their screws, the same build as TTY-02."""
    parts = [
        f"<rect x='4' y='4' width='{W - 8}' height='{H - 8}' rx='12' fill='url(#pg)'/>",
        f"<rect x='4.5' y='4.5' width='{W - 9}' height='{H - 9}' rx='11.5' stroke='{EDGE}'/>",
        f"<path d='M16 5.5H{W - 16}' stroke='#fff' stroke-opacity='.07'/>",
    ]
    for ex in (EAR, W - EAR):  # the seam between rack ear and faceplate
        parts.append(f"<path d='M{ex} 12V{H - 12}' stroke='#000' stroke-opacity='.55'/>"
                     f"<path d='M{ex + 1} 12V{H - 12}' stroke='#fff' stroke-opacity='.04'/>")
    for sx, sy, a in ((22, 26, 20), (22, H - 26, 110), (W - 22, 26, 70), (W - 22, H - 26, 150)):
        parts.append(screw(sx, sy, r=5.2, angle=a))
    return "".join(parts)


def _groove(x0: float, x1: float, y: float) -> str:
    """An engraved hairline: a shadow with a faint lit edge under it."""
    return (f"<path d='M{fmt(x0)} {fmt(y - 0.5)}H{fmt(x1)}' stroke='#000' stroke-opacity='.6'/>"
            f"<path d='M{fmt(x0)} {fmt(y + 0.5)}H{fmt(x1)}' stroke='#fff' stroke-opacity='.05'/>")


def _recess(x: float, y: float, w: float, h: float, rx: float) -> str:
    """A dark window set into the face, lit from below like the terminal's bezel."""
    return (f"<rect x='{fmt(x)}' y='{fmt(y)}' width='{fmt(w)}' height='{fmt(h)}' rx='{fmt(rx)}' fill='#07040D'/>"
            f"<rect x='{fmt(x + 0.5)}' y='{fmt(y + 0.5)}' width='{fmt(w - 1)}' height='{fmt(h - 1)}' "
            f"rx='{fmt(rx - 0.5)}' stroke='url(#lip)'/>")


def window() -> str:
    sx, sy, sw, sh = SCREEN
    return (_recess(sx - 4, sy - 4, sw + 8, sh + 8, 9)
            + f"<rect x='{fmt(sx)}' y='{fmt(sy)}' width='{fmt(sw)}' height='{fmt(sh)}' rx='6' fill='{BG}'/>")


def glass() -> str:
    sx, sy, sw, sh = SCREEN
    return (
        f"<rect x='{fmt(sx)}' y='{fmt(sy)}' width='{fmt(sw)}' height='{fmt(sh)}' rx='6' fill='url(#glass)'/>"
        f"<path d='M{fmt(sx + 6)} {fmt(sy)}H{fmt(sx + sw * 0.62)}L{fmt(sx + sw * 0.5)} {fmt(sy + sh * 0.55)}H{fmt(sx)}V{fmt(sy + 6)}Z' fill='url(#sheen)'/>"
    )


def scan_line(cls: str, strength: float) -> str:
    """A playhead parked off-screen left; its animation carries it across.

    The soft band is masked to the segment shapes, so it only brightens the
    unlit LEDs it passes over and never touches the lit ones or bar heights.
    """
    sx, sy, sw, sh = SCREEN
    return (
        f"<g clip-path='url(#scr)' opacity='{fmt(strength)}'>"
        f"<g mask='url(#segs)'><rect class='{cls}' x='{fmt(sx - 110)}' y='{fmt(TOP)}' width='100' "
        f"height='{fmt(FLOOR - TOP)}' fill='url(#scan)'/></g>"
        f"<rect class='{cls}' x='{fmt(sx - 10.8)}' y='{fmt(sy)}' width='0.8' height='{fmt(sh)}' "
        f"fill='{CYAN}' opacity='.5'/></g>"
    )


def cap_keyframes(lv: list[int]) -> str:
    """One keyframe set per distinct bar height: the cap drops n segments to the floor."""
    return "".join(f"@keyframes c{n}{{from{{transform:translateY({fmt(n * SEG)}px)}}to{{transform:none}}}}"
                   for n in sorted(set(lv)) if n > 0)


def bands(lv: list[int], first_slot: int) -> str:
    """Unlit matrix, lit segments revealed by an animated level mask, peak caps.

    Bars and caps step together (steps(n,end), one segment per STEP_S), so a
    cap always sits on the highest segment lit so far and only bounces once
    the bar is complete.
    """
    unlit = f"<g opacity='.13'>{''.join(_use('col', s) for s in range(SLOTS))}</g>"
    speed = SWEEP / INTRO_DUR
    lead0 = SCREEN[0] - 10  # where the playhead's leading edge starts

    masks, lit, solid, caps = [], [], [], []
    for i, n in enumerate(lv):
        if n <= 0:
            continue
        slot = first_slot + i
        x = slot_x(slot)
        delay = round(INTRO_T0 + (x + BAR_W / 2 - lead0) / speed, 2)
        dur = round(STEP_S * n, 2)
        done = f"{delay + dur:.2f}s"
        masks.append(f"<rect class='b' style='animation-delay:{delay:.2f}s;animation-duration:{dur:.2f}s;"
                     f"animation-timing-function:steps({n},end)' x='{fmt(x - 1)}' y='{fmt(FLOOR - n * SEG)}' "
                     f"width='{fmt(BAR_W + 2)}' height='{fmt(n * SEG)}' fill='#fff'/>")
        lit.append(_use(f"k{n}", slot))
        # Unmasked twin that switches on the moment the rise ends. In Chrome
        # nothing changes; in an engine that never repaints an animated mask
        # the bars still turn up instead of staying dark forever.
        solid.append(_use(f"k{n}", slot, f" class='f' style='animation-delay:{done}'"))
        cap_y = FLOOR - n * SEG + SEG_GAP / 2 - 4.2
        caps.append(
            f"<g style='animation:c{n} {dur:.2f}s steps({n},end) {delay:.2f}s backwards,"
            f"hide 0s {delay + STEP_S:.2f}s backwards'>"
            f"<rect class='h' style='animation-delay:{done}' x='{fmt(x)}' y='{fmt(cap_y)}' "
            f"width='{fmt(BAR_W)}' height='2' rx='1' fill='#F4FAFF'/></g>")

    sx, sy, sw, sh = SCREEN
    lvmask = (f"<mask id='lv' maskUnits='userSpaceOnUse' x='{fmt(sx)}' y='{fmt(sy)}' "
              f"width='{fmt(sw)}' height='{fmt(sh)}'>{''.join(masks)}</mask>")
    return (lvmask + unlit + scan_line("i", 1) + scan_line("s", 0.6)
            + f"<g filter='url(#gl)'><g mask='url(#lv)'>{''.join(lit)}</g>"
              f"{''.join(solid)}{''.join(caps)}</g>")


def axis(marks: list[tuple[float, str, bool]]) -> str:
    """Month ticks printed under the window, ending in a NOW mark at the right.

    Months stay in DIM so the readout labels below outrank them; only the
    year mark and NOW are bright.
    """
    y0 = AXIS_Y
    # 11px keeps a month that starts three columns before NOW (SEP in the
    # real data) clear of it even at the worst-case glyph width
    size, spacing = 11, 1.0
    now_x = slot_x(SLOTS - 1) + BAR_W
    now_left = now_x - _label_w("NOW", size, spacing)
    out = [f"<path d='M{fmt(now_x - 0.5)} {fmt(y0)}v5' stroke='{CYAN}' stroke-opacity='.8'/>",
           label(now_x, y0 + 17, "NOW", size=size, color=CYAN, anchor="end", spacing=spacing)]
    for x, name, jan in marks:
        if x + _label_w(name, size, spacing) + 6 > now_left:
            continue  # would collide with NOW
        out.append(f"<path d='M{fmt(x + 0.5)} {fmt(y0)}v5' stroke='{TEXT if jan else FAINT}' "
                   f"stroke-opacity='{'.7' if jan else '1'}'/>")
        out.append(label(x, y0 + 17, name, size=size, color=TEXT if jan else DIM, spacing=spacing))
    return "".join(out)


def awaiting() -> str:
    """The axis band without data: one centred note between two hairlines."""
    text, size, spacing = "AWAITING DATA", 10, 1.8
    half = _label_w(text, size, spacing) / 2
    cx, ly = W / 2, AXIS_Y + 17
    rule_y = fmt(ly - size * 0.35)
    return (f"<path d='M{fmt(MX0)} {rule_y}H{fmt(cx - half - 12)}M{fmt(cx + half + 12)} {rule_y}H{fmt(MX1)}' "
            f"stroke='{EDGE}'/>"
            + label(cx + spacing / 2, ly, text, size=size, color=DIM, anchor="middle", spacing=spacing))


def _led_socket(cx: float, cy: float) -> str:
    return f"<circle cx='{fmt(cx)}' cy='{fmt(cy)}' r='3.6' fill='#120A1E' stroke='{EDGE}'/>"


def header(model: str, has_data: bool) -> str:
    """Bold model code, dim product line, a groove, then the LED group: TTY-02's layout.

    SIGNAL is the status LED (green with data; red without, blinking until
    IDLE_S and then resting lit); the two mode LEDs only light when there is
    something to scale and hold.
    """
    x = EDGE_X + 4
    out = [label(x, HEAD_Y, model, size=11, color=TEXT, weight=700, spacing=2)]
    x += _label_w(model, 11, 2) + 8
    out.append(label(x, HEAD_Y, CAPTION, size=8.5, color=DIM, spacing=1.8))
    groove_from = x + _label_w(CAPTION, 8.5, 1.8) + 14

    x = W - EDGE_X - 4
    for name, color in (("PEAK HOLD", MAGENTA), ("SQRT SCALE", CYAN), ("SIGNAL", None)):  # right to left
        status = color is None
        lit = has_data or status
        out.append(label(x, HEAD_Y, name, size=9, color=DIM if lit else FAINT, anchor="end", spacing=1.6))
        lx = x - _label_w(name, 9, 1.6) - 10
        out.append(_led_socket(lx, LED_Y))
        if status:
            out.append(led(lx, LED_Y, GREEN if has_data else RED, r=2.6, cls="" if has_data else "blink"))
        elif has_data:
            out.append(led(lx, LED_Y, color, r=2.6))
        else:
            out.append(f"<circle cx='{fmt(lx)}' cy='{fmt(LED_Y)}' r='2.6' fill='{FAINT}' opacity='.5'/>")
        x = lx - 20
    if x + 4 - groove_from > 40:
        out.append(_groove(groove_from, x + 4, LED_Y))
    return "".join(out)


def readouts(items: list[tuple[str, str, str, str]]) -> str:
    """Four LED readouts: (label, value, unit, colour) each.

    Each window holds a row of 5x7 character cells whose unlit dots stay
    visible, so it reads as a built display with the value right-aligned in
    it; the unit is printed at the window's right end, as on a counter.
    """
    gap, pad = 12.0, 12.0
    x0, y0, h = EDGE_X, READOUT_Y, READOUT_H
    w = (W - 2 * EDGE_X - gap * (len(items) - 1)) / len(items)
    cells = max(3, max(len(v) for _, v, _, _ in items))
    cols = dotmatrix.measure("0" * cells)
    # three cells at full size; more cells shrink the dots, never the unit's room
    pitch = min(3.6, 70 / cols)
    r_lit = pitch * 0.4
    fy = y0 + (h - 6 * pitch) / 2
    field_end = pad + cols * pitch + r_lit
    room = w - pad - (field_end + 10)
    longest = max(len(u) for _, _, u, _ in items)
    usize = min(10.0, (room / longest - 1.0) / 0.62) if longest else 10.0

    cell_dots = "".join(f"<circle cx='{fmt((c + .5) * pitch)}' cy='{fmt((r + .5) * pitch)}' r='{fmt(pitch * .36)}'/>"
                        for r in range(7) for c in range(5))
    out = [f"<pattern id='dm' width='{fmt(6 * pitch)}' height='{fmt(7 * pitch)}' patternUnits='userSpaceOnUse' "
           f"x='{fmt(-pitch / 2)}' y='{fmt(-pitch / 2)}'><g fill='{OFF_DOT}'>{cell_dots}</g></pattern>"]
    glow = []
    for i, (name, value, unit, color) in enumerate(items):
        x = x0 + i * (w + gap)
        fx = x + pad
        out.append(label(x + 2, y0 - 7, name, size=11, color=SILK, spacing=1.6))
        out.append(_recess(x, y0, w, h, 5))
        out.append(f"<g transform='translate({fmt(fx)} {fmt(fy)})'>"
                   f"<rect x='{fmt(-pitch / 2)}' y='{fmt(-pitch / 2)}' width='{fmt(6 * cells * pitch)}' "
                   f"height='{fmt(7 * pitch)}' fill='url(#dm)'/></g>")
        vx = fx + (cols - dotmatrix.measure(value)) * pitch  # right-aligned on the cell grid
        glow.append(dotmatrix.render(value, vx, fy, pitch, radius=r_lit, lit=color, off=None))
        if unit:
            out.append(label(x + w - pad, fy + 6 * pitch + r_lit, unit, size=usize, color=SILK,
                             anchor="end", spacing=1.0))
    return "".join(out) + f"<g class='on' filter='url(#gs)'>{''.join(glow)}</g>"


def no_signal() -> str:
    """NO SIGNAL centred in the window on a plate whose edges fall in the
    gaps between segments, so it never cuts an LED in half."""
    text, pitch = "NO SIGNAL", 5.0
    width = dotmatrix.measure(text) * pitch
    x = SCREEN[0] + (SCREEN[2] - width) / 2
    y = TOP + (FLOOR - TOP - 6 * pitch) / 2
    margin = 8
    mid_slot = SLOTS / 2
    half_slots = math.ceil((width / 2 + margin) / PITCH - 0.5) + 0.5
    px0, px1 = MX0 + (mid_slot - half_slots) * PITCH, MX0 + (mid_slot + half_slots) * PITCH
    mid_y = y + 3 * pitch
    half_rows = math.ceil((3 * pitch + margin) / SEG)
    py0, py1 = mid_y - half_rows * SEG, mid_y + half_rows * SEG
    return (f"<rect x='{fmt(px0)}' y='{fmt(py0)}' width='{fmt(px1 - px0)}' "
            f"height='{fmt(py1 - py0)}' rx='2' fill='{BG}' opacity='.9'/>"
            f"<g class='nosig' filter='url(#gl)'>"
            f"{dotmatrix.render(text, x, y, pitch, lit=MAGENTA, off=None)}</g>")


# --- panel ------------------------------------------------------------------------------
def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _short_date(iso: str | None) -> str:
    """'ON SEP 9': the 'on' keeps the day from reading as part of the count."""
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"on {MONTHS[d.month - 1]} {d.day}"


def render(ctx: dict) -> dict[str, str]:
    content = ctx["content"]
    data = ctx.get("data")
    summary = summarize(data) if data else None
    has_data = bool(summary and summary["weeks"])
    login = content.get("login", "")
    model = str((content.get("spectrum") or {}).get("model", MODEL))

    css, lv = CSS, []
    body = [chassis(), header(model, has_data), window()]
    if has_data:
        weeks = summary["weeks"]
        first = SLOTS - len(weeks)
        lv = levels(weeks)
        css += cap_keyframes(lv)
        body.append(bands(lv, first))
        body.append(glass())
        body.append(axis(month_marks(weeks, first)))
        best = summary["best_day"]
        total, cur, longest = summary["total"], summary["current_streak"], summary["longest_streak"]
        body.append(_groove(EDGE_X, W - EDGE_X, GROOVE_Y))
        body.append(readouts([
            ("TOTAL", str(total), _plural(total, "contribution", "contributions"), CYAN),
            ("CURRENT STREAK", str(cur), _plural(cur, "day", "days"), _mix(CYAN, PURPLE, .5)),
            ("LONGEST STREAK", str(longest), _plural(longest, "day", "days"), _mix(PURPLE, MAGENTA, .25)),
            ("BEST DAY", str(best["count"]), _short_date(best["date"]), MAGENTA),
        ]))
        desc = (f"{login}'s GitHub contributions over the last 12 months as a spectrum analyzer, "
                f"one LED bar per week on a square-root scale. Total {total} "
                f"{_plural(total, 'contribution', 'contributions')}, current streak {cur} "
                f"{_plural(cur, 'day', 'days')}, longest streak {longest} "
                f"{_plural(longest, 'day', 'days')}, best day {best['count']} "
                f"{_plural(best['count'], 'contribution', 'contributions')}"
                + (f" on {best['date']}." if best["date"] else "."))
    else:
        body.append(f"<g opacity='.08'>{''.join(_use('col', s) for s in range(SLOTS))}</g>")
        body.append(no_signal())
        body.append(glass())
        body.append(awaiting())
        body.append(_groove(EDGE_X, W - EDGE_X, GROOVE_Y))
        body.append(readouts([(n, "--", "", DIM) for n in
                              ("TOTAL", "CURRENT STREAK", "LONGEST STREAK", "BEST DAY")]))
        desc = "Contribution spectrum analyzer showing NO SIGNAL: GitHub data was unavailable at render time."

    svg = svg_doc(W, H, "".join(body), title=f"{model} contribution spectrum", desc=desc,
                  css=css, defs=defs(lv))
    return {"spectrum.svg": svg}
