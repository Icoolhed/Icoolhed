"""contributions.png: the last 12 months of contributions as a ridgeline.

One point per week, oldest on the left. Height is the square root of the
week's count, so a quiet week still shows next to a busy one; the exact
numbers are in the caption. Needs GitHub data; renders nothing without it.
The sky follows the time of day like the hero's (see sky.py); after dark a
few stars twinkle, and a beacon always blinks on the crest of the current week.
"""

from __future__ import annotations

import math
from datetime import date

from github_data import summarize
from pixel import BLUE, BONE, EMBER, INK, NAVY, NIGHT, SAND, Canvas, apng, fbm, hash01, ramp
from sky import light_for

W, H = 360, 104
LEFT, RIGHT = 12, 348
GROUND = 86          # y of a week with zero contributions
PEAK = 58            # pixels the busiest week rises above GROUND
FRAMES, FRAME_MS = 16, 250  # a 4 s loop
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _curve(values: list[float]) -> list[float]:
    """Cosine-interpolate one value per week into one height per pixel column."""
    span = (RIGHT - LEFT) / max(1, len(values) - 1)
    out = []
    for x in range(W):
        p = min(max((x - LEFT) / span, 0.0), len(values) - 1.0)
        i = min(int(p), len(values) - 2)
        t = (1 - math.cos((p - i) * math.pi)) / 2
        out.append(values[i] * (1 - t) + values[i + 1] * t)
    return out


def render(ctx: dict) -> dict:
    data = ctx.get("data")
    if not data:
        return {}
    light = light_for(ctx)
    s = summarize(data)
    weeks = s["weeks"]
    if len(weeks) < 2:
        return {}
    top = max(1, max(w["count"] for w in weeks))
    front = [math.sqrt(w["count"] / top) for w in weeks]
    # The far ridge is the same data blurred over five weeks, so it reads as foothills.
    kernel = (1, 2, 3, 2, 1)
    back = [sum(k * front[min(max(i + j - 2, 0), len(front) - 1)] for j, k in enumerate(kernel)) / 9
            for i in range(len(front))]

    c = Canvas(W, H)
    for y in range(GROUND):
        for x in range(W):
            c.px[y][x] = ramp((y / GROUND) ** 2.4 * 0.75, light.ramp("plain", x, y), x, y)

    for x, v in enumerate(_curve(back)):
        crest = int(GROUND - 3 * min(1.0, v * 8) - v * (PEAK + 10))
        for y in range(crest, GROUND):
            c.px[y][x] = ramp(0.25 + 0.5 * (1 - (y - crest) / max(1, GROUND - crest)),
                              light.ramp("hills", x, y), x, y)

    for x, v in enumerate(_curve(front)):
        crest = int(GROUND - v * PEAK)
        for y in range(crest, H):
            if y >= GROUND:  # the plain everything stands on
                c.px[y][x] = ramp(0.35 * (1 - (y - GROUND) / (H - GROUND)), [INK, NIGHT, NAVY], x, y)
                continue
            lit = 1 - (y - crest) / max(1, GROUND - crest)
            grain = 0.25 * (fbm(x / 9.0, y / 4.0, seed=61) - 0.5)
            c.px[y][x] = ramp(0.15 + 0.85 * lit ** 1.5 + grain, [NIGHT, NAVY, EMBER, SAND, BONE], x, y)

    span = (RIGHT - LEFT) / (len(weeks) - 1)
    seen = None
    for i, w in enumerate(weeks):
        d = date.fromisoformat(w["start_date"])
        if d.month != seen and (seen is not None or d.day <= 7):
            x = int(LEFT + i * span)
            if x + 17 < W:
                c.set(x, GROUND + 3, BLUE)
                c.set(x, GROUND + 4, BLUE)
                c.text(MONTHS[d.month - 1], x, GROUND + 8, BLUE)
        seen = d.month

    c.text(f"{s['total']:,} contributions", 12, 10, BONE, outline=INK)
    c.text("last 12 months, one point per week", 12, 21, BLUE if light.dark else BONE, outline=INK)
    best = s["best_day"]
    if best["date"]:
        line = f"best day {best['count']}  /  longest streak {s['longest_streak']} d"
        c.text(line, 12, 32, SAND, outline=INK)

    stars = [(int(hash01(i, 21) * W), int(hash01(i, 22) * GROUND * 0.6), i) for i in range(90)]
    stars = [(x, y, i) for x, y, i in stars
             if c.px[y][x] in (INK, NIGHT) and hash01(i, 26) < light.stars]
    now_x, now_y = int(RIGHT), int(GROUND - front[-1] * PEAK) - 3
    frames = []
    for f in range(FRAMES):
        frame = c.copy()
        for x, y, i in stars:
            if hash01(i, 24) < 0.35 and math.sin(2 * math.pi * (f / FRAMES + hash01(i, 25))) > 0.6:
                continue
            frame.px[y][x] = BONE if hash01(i, 23) > 0.75 else BLUE
        if f % 8 < 3:  # the beacon on the current week: lit for three frames in eight
            for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                frame.set(now_x + dx, now_y + dy, BONE if (dx, dy) == (0, 0) else EMBER)
        else:
            frame.set(now_x, now_y, EMBER)
        frames.append(frame)
    return {"contributions.png": apng(frames, FRAME_MS)}
