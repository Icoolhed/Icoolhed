"""hero.png: a dithered sky over three ridgelines that follows what is really going on.

The scene is generated, not a photo, but most of what happens in it is live:

  light     the sun's actual elevation at the place in profile.json (sky.py)
  moon      its real phase, up from sunset to sunrise
  weather   cloud cover, rain and snowfall at that place (conditions.py)
  aurora    green curtains on dark nights when the planetary Kp index is 5 or more
  season    snow on the two far ridges and the cabin roof in winter
  cabin     the window is lit, and the chimney smokes, if there were
            contributions today or yesterday
  meteors   one shooting star per contribution today, at most six per loop
  stars     one star per contribution in the last 12 months, at most 400
  wind      rain, snow and the chimney smoke lean with the real wind
  birds     three of them circle while the sun is up and it is dry
  december  lights on the cabin from 1 December to 6 January, fireworks at New Year

The image is a 9.6 s looping animation. The ridges and the text stay still.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from pixel import (BLUE, BONE, EMBER, GREEN, INK, NAVY, NIGHT, SAND, Canvas, apng, fbm, hash01,
                   ramp, threshold)
from sky import Light, light_for

W, H = 360, 140
HORIZON = 96
SYNODIC = 29.530588853
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)

FRAMES, FRAME_MS = 48, 200   # a 9.6 s loop
CLEAR = -1                   # "shows through" in the layers drawn over the sky
SKY_ROWS = HORIZON + 6
SUN_R = 7
MOON = (292, 36, 25)         # centre x, centre y, radius
MAX_METEORS = 6
FALL = 144                   # precipitation wraps every FALL rows, so the loop is seamless
AURORA_KP = 5.0

# key, base y, height, frequency, seed, haze, takes snow
RIDGES = [
    ("far", 100, 26, 1 / 70.0, 3, 0.62, True),
    ("mid", 114, 24, 1 / 46.0, 5, 0.55, True),
    ("near", 133, 20, 1 / 30.0, 8, 0.35, False),
]
CABIN_X = 292
CABIN = [  # the cabin stands on the near ridge; R roof, # wall, o window, D door
    ".......R.......",
    ".....RRRRR.....",
    "...RRRRRRRRR...",
    ".RRRRRRRRRRRRR.",
    "..###########..",
    "..##ooo######..",
    "..##ooo###DD#..",
    "..##ooo###DD#..",
    "..########DD#..",
]
CHIMNEY = (11, 0)  # column and row of the chimney top, relative to the sprite


def _clamp(v: float) -> float:
    return min(1.0, max(0.0, v))


def _step(a: float, b: float, v: float) -> float:
    t = _clamp((v - a) / (b - a))
    return t * t * (3 - 2 * t)


def moon_age(when: datetime) -> float:
    """Days since the last new moon."""
    return ((when - KNOWN_NEW_MOON).total_seconds() / 86400.0) % SYNODIC


def snow_amount(when: datetime, lat: float) -> float:
    """0..1: full from December to February, fading in through November and out through March."""
    day = when.timetuple().tm_yday
    if lat < 0:
        day = (day + 182) % 365
    from_midwinter = min(abs(day - 15), 365 - abs(day - 15))  # mid-January
    return _clamp((75 - from_midwinter) / 30)


# --- sky ---------------------------------------------------------------------------
def _sun_xy(light: Light) -> tuple[int, int]:
    """The sun keeps to the right-hand sky, clear of the text: due south is where the
    moon hangs at night, and the sun drifts left to right past it over the day."""
    x = 292 + (light.azimuth - 180) * 0.6
    y = HORIZON - 10 - 75 * math.sin(math.radians(light.elev))
    return int(min(W - 20, max(272, x))), int(y)


def _field(seed: int, sx: float, sy: float) -> list[list[float]]:
    return [[fbm(x / sx, y / sy, seed=seed) - 0.5 for x in range(W)] for y in range(SKY_ROWS)]


def _sky_tone(light: Light) -> list[list[float]]:
    sx, sy = _sun_xy(light)
    glow = 0.45 * _clamp((light.elev + 6) / 6)
    tone = []
    for y in range(SKY_ROWS):
        t = y / (SKY_ROWS - 1)
        row = []
        for x in range(W):
            lean = 0.10 * t * (1 - abs(x - sx) / W)  # the horizon is brighter under the sun
            halo = glow * math.exp(-((x - sx) ** 2 + (y - sy) ** 2) / 22.0 ** 2)
            row.append(t ** 1.7 + lean + halo)
        tone.append(row)
    return tone


def _sky(c: Canvas, light: Light, tone: list, wisps: tuple[list, list], cos: float, sin: float) -> None:
    a, b = wisps
    for y in range(SKY_ROWS):
        for x in range(W):
            c.px[y][x] = ramp(tone[y][x] + 0.06 * (cos * a[y][x] + sin * b[y][x]),
                              light.ramp("sky", x, y), x, y)


def _aurora(c: Canvas, strength: float, cos: float, sin: float) -> None:
    """Curtains: a wavy lower edge, bright there and fading upwards, striped by slow rays."""
    for x in range(W):
        rays = _clamp(0.5 + 2.2 * (cos * (fbm(x / 7.0, seed=71) - 0.5) + sin * (fbm(x / 7.0, seed=73) - 0.5)))
        for edge, reach, gain in ((36 + 9 * math.sin(x / 37.0) + 5 * math.sin(x / 13.0 + 2), 30, 1.0),
                                  (22 + 7 * math.sin(x / 29.0 + 4), 18, 0.55)):
            for y in range(max(0, int(edge - reach)), int(edge)):
                power = strength * gain * rays * max(0.0, 1 - (edge - y) / reach) ** 1.4 * 1.5
                if power > threshold(x, y) and c.px[y][x] in (INK, NIGHT, NAVY):
                    c.px[y][x] = GREEN


def _stars(c: Canvas, light: Light, count: int, f: int) -> None:
    for i in range(count):
        if hash01(i, 7) >= light.stars:  # the stars come out one by one as it gets darker
            continue
        x, y = int(hash01(i, 1) * W), int(hash01(i, 2) ** 1.6 * HORIZON * 0.62)
        if c.px[y][x] not in (INK, NIGHT):
            continue
        if hash01(i, 4) < 0.35:  # about a third of the stars twinkle, each at its own pace
            beats = 1 + int(hash01(i, 5) * 3)
            if math.sin(2 * math.pi * (beats * f / FRAMES + hash01(i, 6))) > 0.72:
                continue
        c.px[y][x] = BONE if hash01(i, 3) > 0.7 else BLUE


def _meteors(c: Canvas, count: int, f: int) -> None:
    """`count` shooting stars spread over the loop, each on its own path."""
    for m in range(count):
        start = (m * FRAMES // count + int(hash01(m, 91) * 5)) % FRAMES
        x0, y0 = 150 + int(hash01(m, 92) * 190), 3 + int(hash01(m, 93) * 16)
        head = (f - start) % FRAMES
        for k in range(9):  # nine segments, each fading over three frames
            age = head - k
            if 0 <= age < 3:
                for dx in range(4):
                    c.set(x0 - 4 * k - dx, y0 + 2 * k + dx // 2, (BONE, SAND, BLUE)[age])


def _moon_pixels(age: float) -> list[tuple[int, int, int]]:
    cx, cy, r = MOON
    phi = 2 * math.pi * age / SYNODIC
    lx, lz = math.sin(phi), -math.cos(phi)  # sun direction; waxing lights the right limb
    out = []
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            nx, ny = (x - cx) / r, (y - cy) / r
            d2 = nx * nx + ny * ny
            if d2 > 1:
                continue
            nz = math.sqrt(1 - d2)
            lit = _step(-0.02, 0.22, nx * lx + nz * lz)  # a crisp terminator, even for a thin crescent
            maria = fbm(nx * 2.2 + 5, ny * 2.2 + 9, seed=31)       # large dark plains
            crater = fbm(nx * 7.0, ny * 7.0, seed=47, octaves=2)   # fine speckle
            albedo = 0.55 + 0.45 * (1 - _step(0.48, 0.62, maria)) - 0.18 * (crater - 0.5)
            tone = 0.05 + 0.95 * lit * albedo                      # 0.05: earthshine
            out.append((x, y, ramp(tone, [INK, NIGHT, BLUE, SAND, BONE, BONE], x, y)))
    return out


def _sun(c: Canvas, light: Light) -> None:
    sx, sy = _sun_xy(light)
    for y in range(sy - SUN_R, sy + SUN_R + 1):
        for x in range(sx - SUN_R, sx + SUN_R + 1):
            if (x - sx) ** 2 + (y - sy) ** 2 <= SUN_R ** 2 and 0 <= y < SKY_ROWS:
                c.set(x, y, BONE)


def _cloud_level(cover: float, field: list) -> float:
    """The noise level above which there is cloud, so that 70% of the reported cover is drawn.

    A fully overcast sky is one flat colour and hides everything else in the
    picture, so even then about a third of the sky stays open.
    """
    values = sorted(0.5 + 1.6 * v for row in field for v in row)
    return values[min(len(values) - 1, int((1 - 0.7 * cover) * len(values)))]


def _clouds(c: Canvas, light: Light, level: float, fields: tuple[list, list], cos: float, sin: float) -> None:
    """Cloud where a slowly morphing noise field rises above `level`, dithered in at the edges."""
    a, b = fields
    for y in range(SKY_ROWS):
        thin = 1 - 0.5 * (y / SKY_ROWS) ** 2  # thinner towards the horizon
        for x in range(W):
            density = 0.5 + 1.6 * (cos * a[y][x] + sin * b[y][x])
            body = (density - level) / 0.14
            if body * thin * 0.9 > threshold(x + 1, y + 2):
                c.px[y][x] = ramp(0.15 + 0.5 * body, light.ramp("cloud", x, y), x, y)


# --- land --------------------------------------------------------------------------
def _crest(base: float, height: float, freq: float, seed: int, x: int) -> int:
    return int(base - height * fbm(x * freq, seed=seed, octaves=5))


def _ridge(c: Canvas, light: Light, key: str, base: float, height: float, freq: float,
           seed: int, haze: float, snow: float) -> None:
    """Fill everything below a noise ridgeline. `haze` lightens the ridge near its crest."""
    for x in range(W):
        top = _crest(base, height, freq, seed, x)
        # Snow lies on the high ground only, and the snowline comes down as winter deepens.
        high = (base - top) / height
        cap = 45 * snow * max(0.0, high - (0.72 - 0.3 * snow)) * (0.6 + 0.8 * fbm(x / 9.0, seed=seed + 20))
        for y in range(max(0, top), H):
            depth = (y - top) / max(1.0, H - top)
            slope = 0.12 * (fbm(x / 14.0, y / 5.0, seed=seed + 9) - 0.5)
            if y - top < cap and 1.2 - (y - top) / cap > threshold(x, y):
                c.px[y][x] = BONE
            else:
                c.px[y][x] = ramp(haze * (1 - depth) ** 2.2 + slope, light.ramp(key, x, y), x, y)


def _cabin_ground() -> int:
    _, base, height, freq, seed, _, _ = RIDGES[-1]
    return max(_crest(base, height, freq, seed, CABIN_X + col) for col in range(2, 13))


def _cabin(c: Canvas, snow: float) -> None:
    top = _cabin_ground() - len(CABIN) + 1
    for r, line in enumerate(CABIN):
        for col, ch in enumerate(line):
            if ch == ".":
                continue
            colour = {"R": NAVY, "#": NIGHT, "D": INK, "o": NIGHT}[ch]
            if ch == "R" and snow > 0.3 and (r < 2 or (col + r) % 2 == 0):
                colour = BONE  # snow on the roof
            c.set(CABIN_X + col, top + r, colour)
    for dy in (0, 1):
        c.set(CABIN_X + CHIMNEY[0], top + CHIMNEY[1] + dy, NIGHT)


def _cabin_life(c: Canvas, light: Light, home: bool, lean: float, festive: bool, f: int) -> None:
    """The window and, when someone is home, a flickering lamp and chimney smoke."""
    top = _cabin_ground() - len(CABIN) + 1
    lamp = NIGHT
    if home:
        lamp = EMBER if hash01(f // 3, 77) > 0.8 else SAND
    for r, line in enumerate(CABIN):
        for col, ch in enumerate(line):
            if ch == "o":
                c.set(CABIN_X + col, top + r, lamp)
    if festive:  # a string of lights along the eaves
        for col in range(1, 14, 2):
            on = (col // 2 + f // 4) % 3
            c.set(CABIN_X + col, top + 4, (EMBER, SAND, BONE)[on])
    if not home:
        return
    sx, sy = CABIN_X + CHIMNEY[0], top + CHIMNEY[1] - 1
    for puff in range(4):
        age = (f + puff * FRAMES // 4) % FRAMES
        if age >= 26 or (age > 16 and (age + puff) % 2):
            continue
        x = sx - round(lean * age / 2.5) + round(math.sin(age / 4.0 + puff))
        c.set(x, sy - age // 3, BLUE if light.dark else BONE)


def _birds(c: Canvas, f: int) -> None:
    """Three birds circling; wings up on one beat, flat on the next."""
    for b in range(3):
        turn = 2 * math.pi * (f / FRAMES + b * 0.31)
        x = int(196 + (46 + 12 * b) * math.cos(turn))
        y = int(30 + (9 + 3 * b) * math.sin(turn))
        up = (f + b) % 4 < 2
        for dx in (-2, -1, 1, 2):
            c.set(x + dx, y - (abs(dx) - 1 if up else 0), INK)
        c.set(x, y, INK)


def _fireworks(c: Canvas, f: int) -> None:
    """Three bursts per loop: a ring of sparks that spreads, sags and fades."""
    for b, (cx, cy) in enumerate(((228, 30), (150, 22), (318, 40))):
        age = (f - b * FRAMES // 3) % FRAMES
        if age > 13:
            continue
        for s in range(22):
            a = 2 * math.pi * s / 22
            r = 3 + age * 1.8
            x, y = int(cx + r * math.cos(a)), int(cy + r * math.sin(a) * 0.8 + age * age * 0.06)
            if 0 <= y < SKY_ROWS and (age < 9 or (s + age) % 2):
                c.set(x, y, (BONE, SAND, EMBER)[(b + (age > 6)) % 3])


def _precipitation(c: Canvas, rain: float, snow: float, lean: float, f: int) -> None:
    if snow > 0:
        for i in range(min(160, int(70 + snow * 400))):
            y = (int(hash01(i, 53) * FALL) + 3 * f) % FALL
            x = (int(hash01(i, 51) * (W + 120)) - 60 - round(lean * y * 0.8)
                 + round(2 * math.sin(2 * math.pi * (2 * f / FRAMES + hash01(i, 52)))))
            c.set(x, y, BONE)
            if hash01(i, 54) > 0.7:
                c.set(x + 1, y, BONE)
    elif rain > 0:
        for i in range(min(150, int(35 + rain * 250))):
            y = (int(hash01(i, 61) * FALL) + 9 * f) % FALL
            x = int(hash01(i, 62) * (W + 120)) - 60 - round(lean * y * 0.5)
            for k in range(4):
                c.set(x - round(lean * k * 0.5), y + k, BLUE)


def _overlay(c: Canvas, layer: Canvas) -> None:
    for y in range(H):
        row, over = c.px[y], layer.px[y]
        for x in range(W):
            if over[x] != CLEAR:
                row[x] = over[x]


def render(ctx: dict) -> dict:
    content, data, light = ctx["content"], ctx.get("data"), light_for(ctx)
    cond = ctx.get("cond") or {}
    cover, rain, snowfall, kp = (cond.get(k) or 0.0 for k in ("cloud", "rain", "snow", "kp"))
    recent = [d["count"] for d in data["calendar"][-2:]] if data else []
    today = recent[-1] if recent else 0
    home = any(recent)
    season = snow_amount(ctx["when"], content["place"]["lat"])
    stars = min(400, sum(d["count"] for d in data["calendar"][-365:])) if data else 140
    # The picture looks south, so east is on the left: a west wind blows things to the left.
    lean = -math.sin(math.radians(cond.get("wdir") or 0.0)) * min(1.0, (cond.get("wind") or 0.0) / 10)
    when = ctx["when"]
    festive = (when.month == 12) or (when.month == 1 and when.day <= 6)
    new_year = (when.month, when.day) in ((12, 31), (1, 1))
    night = light.stars > 0.6
    aurora = _clamp((kp - AURORA_KP + 1.5) / 3) if kp >= AURORA_KP and night else 0.0
    meteors = min(MAX_METEORS, today) if light.elev < -10 else 0

    land = Canvas(W, H, fill=CLEAR)
    for key, base, height, freq, seed, haze, snowy in RIDGES:
        _ridge(land, light, key, base, height, freq, seed, haze, season if snowy else 0.0)
    _cabin(land, season)

    words = Canvas(W, H, fill=CLEAR)
    words.text(content["handle"], 18, 26, BONE, size=4, shadow=INK, outline=INK)
    words.text(content["tagline"], 19, 62, SAND if light.dark else BONE, outline=INK)

    tone = _sky_tone(light)
    wisps = (_field(11, 60.0, 9.0), _field(17, 60.0, 9.0))
    clouds = (_field(23, 48.0, 11.0), _field(29, 48.0, 11.0)) if cover > 0.05 else None
    level = _cloud_level(cover, clouds[0]) if clouds else 0.0
    moon = _moon_pixels(moon_age(ctx["when"])) if light.dark else []

    frames = []
    for f in range(FRAMES):
        turn = 2 * math.pi * f / FRAMES
        cos, sin = math.cos(turn), math.sin(turn)
        c = Canvas(W, H)
        _sky(c, light, tone, wisps, cos, sin)
        if aurora:
            _aurora(c, aurora, cos, sin)
        _stars(c, light, stars, f)
        _meteors(c, meteors, f)
        for x, y, colour in moon:
            c.px[y][x] = colour
        if light.elev > -3:
            _sun(c, light)
        if new_year and night:
            _fireworks(c, f)
        if clouds:
            _clouds(c, light, level, clouds, cos, sin)
        if light.elev > 2 and not rain and not snowfall:
            _birds(c, f)
        _overlay(c, land)
        _cabin_life(c, light, home, lean, festive, f)
        _precipitation(c, rain, snowfall, lean, f)
        _overlay(c, words)
        frames.append(c)
    return {"hero.png": apng(frames, FRAME_MS)}
