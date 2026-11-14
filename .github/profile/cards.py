"""card-<slug>.png: one small dithered, animated card per project in profile.json.

Each card is a night-blue panel with a generated motif, the project's name
and one line about it. The motif is picked by the project's "motif" key.
"""

from __future__ import annotations

import math

from pixel import BLUE, BONE, EMBER, INK, NAVY, NIGHT, SAND, Canvas, apng, fbm, hash01, ramp, text_width

W, H = 224, 112
FRAMES, FRAME_MS = 24, 200  # a 4.8 s loop
MID_X, MID_Y = W // 2, 38   # centre of the motif area


def _rect(c: Canvas, x0: int, y0: int, w: int, h: int, colour: int, fill: int | None = None) -> None:
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            edge = x in (x0, x0 + w - 1) or y in (y0, y0 + h - 1)
            if edge:
                c.set(x, y, colour)
            elif fill is not None:
                c.set(x, y, fill)


def _background(seed: int) -> Canvas:
    c = Canvas(W, H)
    for y in range(H):
        for x in range(W):
            grain = 0.10 * (fbm(x / 30.0, y / 12.0, seed=seed) - 0.5)
            c.px[y][x] = ramp(0.12 + 0.55 * (y / H) ** 1.5 + grain, [INK, NIGHT, NAVY, NAVY], x, y)
    return c


# --- motifs: each draws frame f onto c ---------------------------------------------
def wave(c: Canvas, f: int) -> None:
    """Loopline: a waveform that keeps playing, with a playhead sweeping across it."""
    p = f / FRAMES
    head = 20 + int(p * 184)
    for i in range(46):
        x = 20 + i * 4
        shape = 0.35 + 0.65 * abs(math.sin(i * 0.31) * math.cos(i * 0.13 + 1))
        beat = 0.6 + 0.4 * math.sin(2 * math.pi * ((1 + i % 2) * p + hash01(i, 3)))
        half = max(1, int(27 * shape * beat))
        played = x <= head
        for dy in range(-half, half + 1):
            tone = 1 - abs(dy) / (half + 1)
            colours = [EMBER, SAND, BONE] if played else [NAVY, BLUE, BLUE]
            for dx in range(2):
                c.set(x + dx, MID_Y + dy, ramp(tone, colours, x + dx, MID_Y + dy))
    for y in range(6, 71):
        c.set(head, y, BONE)


def orb(c: Canvas, f: int) -> None:
    """Jarvis: a quiet core with rings travelling outwards, like something listening."""
    p = f / FRAMES
    for y in range(4, 73):
        for x in range(MID_X - 60, MID_X + 61):
            d = math.hypot(x - MID_X, (y - MID_Y) * 1.15)
            if d > 58:
                continue
            ring = 0.5 + 0.5 * math.sin(d * 0.42 - 2 * math.pi * p)
            tone = (1 - d / 58) ** 1.3 * (0.35 + 0.65 * ring)
            if d < 11:
                tone = 1.0 - 0.25 * (d / 11) + 0.1 * math.sin(2 * math.pi * p)
            if tone > 0.06:
                c.px[y][x] = ramp(tone, [NIGHT, NAVY, BLUE, SAND, BONE], x, y)


def racks(c: Canvas, f: int) -> None:
    """isak-sandbox: three rack units; the middle one is being broken and restarted."""
    for unit in range(3):
        x0, y0 = MID_X - 56, 9 + unit * 21
        _rect(c, x0, y0, 112, 17, BLUE, NIGHT)
        for vx in range(x0 + 44, x0 + 106, 3):  # vents
            for vy in range(y0 + 4, y0 + 13, 2):
                c.set(vx, vy, NAVY)
        for led in range(5):
            lx, ly = x0 + 6 + led * 7, y0 + 7
            if unit == 1:
                on = (f // 3) % 2 == 0
                colour = EMBER if on else NIGHT
                if f >= FRAMES - 6:  # it comes back at the end of the loop
                    colour = SAND if led <= (f - (FRAMES - 6)) else NIGHT
            else:
                colour = SAND if hash01(f // 2, unit, led) > 0.35 else NAVY
            _rect(c, lx, ly, 3, 3, colour, colour)


def form(c: Canvas, f: int) -> None:
    """Formcraft: a form filling itself in, field by field, then the button lights up."""
    x0 = MID_X - 62
    for row in range(3):
        y0 = 7 + row * 17
        _rect(c, x0, y0, 124, 12, BLUE, NIGHT)
        start = row * 6
        typed = max(0, min(14 - row * 3, f - start))
        for k in range(typed):  # typed characters as small blocks
            _rect(c, x0 + 5 + k * 7, y0 + 4, 5, 4, BONE, BONE)
        if start <= f < start + 6 and f % 2 == 0:  # cursor
            _rect(c, x0 + 5 + typed * 7, y0 + 3, 2, 6, SAND, SAND)
    done = f >= 18
    _rect(c, x0, 60, 44, 11, SAND if done else NAVY, EMBER if done else NIGHT)
    c.text("save", x0 + 10, 62, BONE if done else BLUE)
    _rect(c, x0 + 56, 61, 9, 9, BLUE, NIGHT)
    if f >= 14:  # the checkbox ticks
        for dx, dy in ((2, 4), (3, 5), (4, 4), (5, 3), (6, 2)):
            c.set(x0 + 56 + dx, 61 + dy, SAND)


def code(c: Canvas, f: int) -> None:
    """Rackcode: commands typed into a terminal while the racks beside it wake up."""
    lines = ["> buy rack", "> wire 4", "> run"]
    budget = f + 1
    for i, line in enumerate(lines):
        shown = line[:max(0, min(len(line), budget * 2))]
        budget -= (len(line) + 1) // 2 + 1
        c.text(shown, 22, 12 + i * 14, SAND if i == 2 else BONE)
        if 0 < len(shown) < len(line) or (i == 2 and len(shown) == len(line) and f % 2):
            _rect(c, 22 + len(shown) * 6, 12 + i * 14, 4, 7, BONE, BONE)
    awake = max(0, f - 14)
    for r in range(3):
        x0 = 128 + r * 26
        _rect(c, x0, 12, 20, 56, BLUE, NIGHT)
        for slot in range(6):
            lit = awake > slot + r and hash01(f // 2, r, slot) > 0.25
            _rect(c, x0 + 4, 17 + slot * 8, 12, 4, SAND if lit else NAVY, SAND if lit else NAVY)


def moth(c: Canvas, f: int) -> None:
    """Artspecifikationer: a specimen with slowly beating wings and a measured wingspan."""
    beat = 0.45 + 0.55 * abs(math.cos(math.pi * f / FRAMES))
    cx = MID_X
    for y in range(6, 66):
        for x in range(cx - 46, cx + 47):
            u, v = abs(x - cx) / beat, y - 34
            upper = ((u - 20) / 21) ** 2 + ((v + 9) / 15) ** 2
            lower = ((u - 13) / 13) ** 2 + ((v - 13) / 11) ** 2
            inside = min(upper, lower)
            if inside <= 1 and u >= 1:
                spots = fbm(u / 6.0, v / 6.0, seed=83)
                c.px[y][x] = ramp(0.25 + 0.75 * (1 - inside) * (0.6 + 0.8 * spots),
                                  [EMBER, EMBER, SAND, BONE], x, y)
    for y in range(18, 52):  # body and antennae
        c.set(cx, y, INK)
        c.set(cx - 1, y, INK if 24 < y < 46 else c.px[y][cx - 1])
    for k in range(7):
        c.set(cx - 1 - k, 17 - k, BONE)
        c.set(cx + k, 17 - k, BONE)
    for x in range(cx - 42, cx + 43):  # the dimension line under the specimen
        c.set(x, 68, BLUE)
    for x in (cx - 42, cx + 42):
        for y in range(65, 72):
            c.set(x, y, BLUE)
    c.text("52 mm", cx + 48, 64, BLUE)


MOTIFS = {"wave": wave, "orb": orb, "racks": racks, "form": form, "code": code, "moth": moth}


def render(ctx: dict) -> dict:
    out = {}
    for n, project in enumerate(ctx["content"].get("projects", [])):
        base = _background(100 + n)
        name = project["name"]
        base.text(name, min(12, (W - text_width(name, 2)) // 2), 78, BONE, size=2, outline=INK)
        base.text(project["line"], 12, 98, SAND, outline=INK)
        draw = MOTIFS[project["motif"]]
        frames = []
        for f in range(FRAMES):
            c = base.copy()
            draw(c, f)
            frames.append(c)
        out[f"card-{project['slug']}.png"] = apng(frames, FRAME_MS)
    return out
