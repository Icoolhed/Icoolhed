#!/usr/bin/env python3
"""Render the profile images (dithered PNGs).

    python .github/profile/render.py --out dist              # CI: live data via GITHUB_TOKEN
    python .github/profile/render.py --out dist --data d.json  # local: cached data
    python .github/profile/render.py --out dist --only hero --at 2026-06-21T12:00
    python .github/profile/render.py --out dist --cond '{"cloud": 0.4, "snow": 0.2, "wind": 6, "kp": 6}'

The handle, tagline and place live in profile.json at the repo root. The sky
follows the sun at that place for the moment of rendering (--at, in UTC,
overrides the clock) and the weather and aurora activity there (--cond
overrides those). Numbers only
ever come from the GitHub API; a panel that needs data it cannot get is
skipped rather than drawn with invented values. Standard library only, so CI
needs nothing beyond a Python install.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Panel name -> module in this folder exposing render(ctx) -> {filename: png_bytes}.
PANELS = {
    "hero": "hero",        # hero.png
    "terrain": "terrain",  # contributions.png (needs data)
    "cards": "cards",      # card-<slug>.png per project
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="dist", help="output directory")
    ap.add_argument("--content", default=str(HERE.parent.parent / "profile.json"))
    ap.add_argument("--data", help="read GitHub data from this JSON file instead of the API")
    ap.add_argument("--only", help="comma-separated panel names: " + ",".join(PANELS))
    ap.add_argument("--at", help="render for this UTC time (ISO 8601) instead of now")
    ap.add_argument("--cond", help="JSON with cloud (0..1), rain, snow, wind, wdir and kp, instead of fetching them")
    ap.add_argument("--require-data", action="store_true",
                    help="exit non-zero if GitHub data can't be fetched (CI: keep the last good render)")
    args = ap.parse_args()

    content = json.loads(Path(args.content).read_text(encoding="utf-8"))
    if args.data:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    else:
        data = importlib.import_module("github_data").fetch(content["login"])
    if data is None and args.require_data:
        print("no GitHub data; refusing to render over the last good panels", file=sys.stderr)
        return 1

    when = datetime.fromisoformat(args.at) if args.at else datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if args.cond:
        cond = json.loads(args.cond)
    else:
        cond = importlib.import_module("conditions").fetch(content["place"])
    ctx = {"content": content, "data": data, "when": when, "cond": cond}
    wanted = args.only.split(",") if args.only else list(PANELS)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for name in wanted:
        for filename, png in importlib.import_module(PANELS[name]).render(ctx).items():
            (out / filename).write_bytes(png)
            print(f"{name:>9}  {filename}  {len(png) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
