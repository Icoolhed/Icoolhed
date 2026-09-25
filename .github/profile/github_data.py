#!/usr/bin/env python3
"""Fetch the numbers the profile is allowed to show, straight from GitHub.

    python .github/profile/github_data.py [login]   # prints the data as JSON

fetch() asks the GraphQL API for one user's contribution calendar and a few
counters, using $GITHUB_TOKEN (CI) or, failing that, the local `gh` CLI. It
never raises: on any problem it warns on stderr and returns None, and the
panels then render without data instead of guessing. summarize() derives the
readouts (totals, streaks, weekly bars) from that data.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API = "https://api.github.com/graphql"
TIMEOUT = 30

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    followers { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER) { totalCount }
    contributionsCollection {
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def _warn(msg: str) -> None:
    print(f"github_data: {msg}", file=sys.stderr)


def _via_api(login: str, token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "icoolhed-profile-renderer",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _via_gh(login: str) -> dict:
    cmd = ["gh", "api", "graphql", "-f", f"query={QUERY}", "-f", f"login={login}"]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    if done.returncode != 0:
        raise RuntimeError(f"gh exited {done.returncode}: {done.stderr.strip()}")
    return json.loads(done.stdout)


def _shape(payload: dict) -> dict | None:
    """GraphQL response -> the flat dict the panels read (see fetch())."""
    if payload.get("errors"):
        _warn("API errors: " + "; ".join(e.get("message", "?") for e in payload["errors"]))
        return None
    user = (payload.get("data") or {}).get("user")
    if not user:
        _warn("user not found")
        return None
    coll = user["contributionsCollection"]
    cal = coll["contributionCalendar"]
    days = [{"date": d["date"], "count": int(d["contributionCount"])}
            for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    if not days:
        _warn("empty contribution calendar")
        return None
    return {
        "login": user["login"],
        # The last calendar day, not the clock, so output is reproducible.
        "fetched_at": days[-1]["date"],
        "total_contributions": int(cal["totalContributions"]),
        "restricted_contributions": int(coll["restrictedContributionsCount"]),
        "followers": int(user["followers"]["totalCount"]),
        "public_repos": int(user["repositories"]["totalCount"]),
        "calendar": days,
    }


def fetch(login: str) -> dict | None:
    """Contribution data for `login`, or None if it cannot be had.

    Shape: {login, fetched_at, total_contributions, restricted_contributions,
    followers, public_repos, calendar: [{date, count}, ...] oldest first}.
    """
    try:
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            payload = _via_api(login, token)
        elif shutil.which("gh"):
            payload = _via_gh(login)
        else:
            _warn("no GITHUB_TOKEN and no gh CLI; rendering without data")
            return None
        return _shape(payload)
    except urllib.error.HTTPError as e:
        _warn(f"HTTP {e.code} from the GitHub API")
    except Exception as e:  # noqa: BLE001 - the renderer must never crash on data
        _warn(f"{type(e).__name__}: {e}")
    return None


# --- derived numbers ---------------------------------------------------------------
def _sunday(d: date) -> date:
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _runs(counts: list[int]) -> list[int]:
    """Length of the active streak ending on each day."""
    out, run = [], 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        out.append(run)
    return out


def _year_before(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - 1, day=28)


def summarize(data: dict) -> dict:
    """Readouts for the spectrum panel, computed from data["calendar"].

    Only the one-year window counts: GitHub pads the calendar's first week
    back to a Sunday, and those padding days are dropped. Everything below
    comes from the days that remain, so total is exactly what the weekly
    bars add up to, and it is the same year GitHub's own "N contributions
    in the last year" covers.

    weeks are Sunday-start (GitHub's own columns), oldest first, at most 53;
    the first one may be partial. The current streak may end yesterday:
    today is not over yet.
    """
    cal = sorted(data.get("calendar") or [], key=lambda d: d["date"])
    if cal:
        start = _year_before(date.fromisoformat(cal[-1]["date"])).isoformat()
        cal = [d for d in cal if d["date"] >= start]
    counts = [int(d["count"]) for d in cal]

    weeks: list[dict] = []
    for day in cal:
        start = _sunday(date.fromisoformat(day["date"])).isoformat()
        if weeks and weeks[-1]["start_date"] == start:
            weeks[-1]["count"] += int(day["count"])
        else:
            weeks.append({"start_date": start, "count": int(day["count"])})
    weeks = weeks[-53:]

    runs = _runs(counts)
    current = 0
    if runs:
        current = runs[-1] if counts[-1] > 0 else (runs[-2] if len(runs) > 1 else 0)

    best = {"date": None, "count": 0}
    for day in cal:  # ">=" so a tie goes to the most recent day
        if int(day["count"]) > 0 and int(day["count"]) >= best["count"]:
            best = {"date": day["date"], "count": int(day["count"])}

    return {
        "total": sum(counts),
        "weeks": weeks,
        "current_streak": current,
        "longest_streak": max(runs, default=0),
        "best_day": best,
        "active_days": sum(1 for c in counts if c > 0),
    }


def _default_login() -> str:
    try:
        content = Path(__file__).resolve().parents[2] / "profile.json"
        return json.loads(content.read_text(encoding="utf-8"))["login"]
    except (OSError, KeyError, ValueError):
        return "Icoolhed"


if __name__ == "__main__":
    result = fetch(sys.argv[1] if len(sys.argv) > 1 else _default_login())
    if result is None:
        sys.exit(1)
    print(json.dumps(result, indent=1))
