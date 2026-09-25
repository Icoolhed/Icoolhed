#!/usr/bin/env python3
"""Render every profile panel to SVG.

    python .github/profile/render.py --out dist              # CI: live data via GITHUB_TOKEN
    python .github/profile/render.py --out dist --data d.json  # local: cached data
    python .github/profile/render.py --out dist --only hero,terminal

Content (names, taglines, terminal lines) lives in profile.json at the repo
root. Numbers only ever come from the GitHub API; a panel that needs data it
cannot get renders without it rather than inventing values. Standard library
only, so CI needs nothing beyond a Python install.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Panel name -> module in this folder exposing render(ctx) -> {filename: svg_text}.
PANELS = {
    "hero": "hero",          # hero.svg, footer.svg
    "terminal": "terminal",  # terminal.svg
    "modules": "modules",    # module-<slug>.svg per project
    "spectrum": "spectrum",  # spectrum.svg (needs data)
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="dist", help="output directory")
    ap.add_argument("--content", default=str(HERE.parent.parent / "profile.json"))
    ap.add_argument("--data", help="read GitHub data from this JSON file instead of the API")
    ap.add_argument("--only", help="comma-separated panel names: " + ",".join(PANELS))
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

    ctx = {"content": content, "data": data}
    wanted = args.only.split(",") if args.only else list(PANELS)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for name in wanted:
        for filename, svg in importlib.import_module(PANELS[name]).render(ctx).items():
            (out / filename).write_text(svg, encoding="utf-8", newline="\n")
            print(f"{name:>9}  {filename}  {len(svg.encode()) / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
