"""Where the sun is, and which colours the scene gets for it.

The panels follow the real time of day at the place in profile.json: the
renderer runs hourly, works out the sun's elevation, and blends between four
looks (night, dusk, sunset, day). Dawn reuses dusk and sunset.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from pixel import BLUE, BONE, EMBER, INK, NAVY, NIGHT, SAND, threshold

J2000 = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)


def sun_position(when: datetime, lat: float, lon: float) -> tuple[float, float]:
    """(elevation, azimuth) of the sun in degrees; azimuth clockwise from north.

    The low-precision formulas from the Astronomical Almanac, good to a
    fraction of a degree, which is far finer than a dithered sky can show.
    """
    n = (when - J2000).total_seconds() / 86400.0
    mean_lon = math.radians((280.460 + 0.9856474 * n) % 360)
    anomaly = math.radians((357.528 + 0.9856003 * n) % 360)
    ecl_lon = mean_lon + math.radians(1.915 * math.sin(anomaly) + 0.020 * math.sin(2 * anomaly))
    tilt = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(tilt) * math.sin(ecl_lon), math.cos(ecl_lon))
    dec = math.asin(math.sin(tilt) * math.sin(ecl_lon))
    sidereal = math.radians(((18.697374558 + 24.06570982441908 * n) % 24) * 15 + lon)
    hour = sidereal - ra
    phi = math.radians(lat)
    elev = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(hour))
    az = math.atan2(math.sin(hour), math.cos(hour) * math.sin(phi) - math.tan(dec) * math.cos(phi))
    return math.degrees(elev), (math.degrees(az) + 180) % 360


# Sun elevation in degrees -> the colour ramps used at that elevation.
#   sky/cloud/far/mid/near: the hero.  plain/hills: the contributions panel.
LOOKS = [
    (-18.0, {  # night
        "sky": [INK, INK, INK, NIGHT, NIGHT, NAVY], "cloud": [NIGHT, NIGHT, NAVY],
        "far": [INK, NIGHT, NAVY, NAVY], "mid": [INK, INK, NIGHT, NAVY], "near": [INK, INK, INK, NIGHT],
        "plain": [INK, INK, NIGHT, NAVY], "hills": [NIGHT, NAVY, BLUE],
    }),
    (-6.0, {  # dusk
        "sky": [INK, INK, NIGHT, NAVY, EMBER, SAND], "cloud": [NIGHT, NAVY, BLUE],
        "far": [NIGHT, NAVY, BLUE, EMBER], "mid": [INK, NIGHT, NAVY, BLUE], "near": [INK, INK, NIGHT, NAVY],
        "plain": [INK, NIGHT, NAVY, EMBER], "hills": [NIGHT, NAVY, BLUE],
    }),
    (0.0, {  # sunset
        "sky": [NIGHT, NAVY, BLUE, EMBER, SAND, BONE], "cloud": [NAVY, BLUE, SAND],
        "far": [NIGHT, NAVY, BLUE, SAND], "mid": [INK, NIGHT, NAVY, BLUE], "near": [INK, INK, NIGHT, NAVY],
        "plain": [NIGHT, NAVY, BLUE, EMBER], "hills": [NIGHT, NAVY, BLUE],
    }),
    (8.0, {  # day
        "sky": [NAVY, NAVY, BLUE, BLUE, BONE, BONE], "cloud": [NAVY, BLUE, BONE],
        "far": [NAVY, BLUE, BLUE, BONE], "mid": [NIGHT, NAVY, BLUE, BLUE], "near": [INK, NIGHT, NAVY, NAVY],
        "plain": [NAVY, NAVY, BLUE, BONE], "hills": [NIGHT, NAVY, NAVY],
    }),
]


class Light:
    """The look for one sun elevation: two neighbouring LOOKS and how far between them."""

    def __init__(self, elev: float):
        self.elev = elev
        self.a, self.b, self.mix = LOOKS[0][1], LOOKS[0][1], 0.0
        for (e0, look0), (e1, look1) in zip(LOOKS, LOOKS[1:]):
            if elev >= e0:
                self.a, self.b = look0, look1
                self.mix = min(1.0, (elev - e0) / (e1 - e0))
        self.stars = min(1.0, max(0.0, (-elev - 3) / 9))  # share of the stars that are out
        self.dark = elev < 3

    def ramp(self, key: str, x: int, y: int) -> list[int]:
        """The ramp for `key` at this pixel. Between two looks the choice itself is dithered."""
        return self.b[key] if self.mix > threshold(x + 3, y + 5) else self.a[key]


def light_for(ctx: dict) -> Light:
    place = ctx["content"]["place"]
    elev, az = sun_position(ctx["when"], place["lat"], place["lon"])
    light = Light(elev)
    light.azimuth = az
    return light
