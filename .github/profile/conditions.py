#!/usr/bin/env python3
"""Fetch what the sky is doing right now: weather at the place, and aurora activity.

    python .github/profile/conditions.py   # prints the conditions as JSON

Weather comes from Open-Meteo and the planetary Kp index from NOAA's Space
Weather Prediction Center; neither needs a key. fetch() never raises: a
source that cannot be reached leaves its values at None, and the hero then
draws a clear, quiet sky instead of guessing.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

TIMEOUT = 15
WEATHER = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=cloud_cover,rain,showers,snowfall")
KP = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-renderer"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _warn(msg: str) -> None:
    print(f"conditions: {msg}", file=sys.stderr)


def fetch(place: dict) -> dict:
    """{cloud: 0..1, rain: mm per 15 min, snow: cm per 15 min, kp: 0..9}, each None if unknown."""
    out = {"cloud": None, "rain": None, "snow": None, "kp": None}
    try:
        now = _get(WEATHER.format(lat=place["lat"], lon=place["lon"]))["current"]
        out["cloud"] = float(now["cloud_cover"]) / 100.0
        out["rain"] = float(now["rain"]) + float(now["showers"])
        out["snow"] = float(now["snowfall"])
    except Exception as e:  # noqa: BLE001 - the renderer must never crash on data
        _warn(f"weather: {type(e).__name__}: {e}")
    try:
        last = _get(KP)[-1]
        out["kp"] = float(last["Kp"] if isinstance(last, dict) else last[1])
    except Exception as e:  # noqa: BLE001
        _warn(f"kp: {type(e).__name__}: {e}")
    return out


if __name__ == "__main__":
    content = json.loads((Path(__file__).resolve().parents[2] / "profile.json").read_text(encoding="utf-8"))
    print(json.dumps(fetch(content["place"])))
