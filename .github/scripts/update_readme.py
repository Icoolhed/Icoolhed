#!/usr/bin/env python3
"""
Regenerates the OVERVIEW section of README.md and appends a CHANGELOG entry,
based on the current codebase and the most recent commit.

Run by .github/workflows/update-readme.yml on every push. Safe to run
locally too: `ANTHROPIC_API_KEY=... python .github/scripts/update_readme.py`

README.md must contain (or will be given, on first run) these markers:

    <!-- OVERVIEW:START -->
    ...rewritten automatically...
    <!-- OVERVIEW:END -->

    <!-- CHANGELOG:START -->
    - **YYYY-MM-DD** — summary
    <!-- CHANGELOG:END -->

Everything outside the markers (title, badges, license, custom sections you
add below the changelog, etc.) is left untouched.
"""

import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone

README_PATH = "README.md"
MAX_CHANGELOG_ENTRIES = 40
MAX_DIFF_CHARS = 12000
MAX_TREE_ENTRIES = 400

OVERVIEW_START = "<!-- OVERVIEW:START -->"
OVERVIEW_END = "<!-- OVERVIEW:END -->"
CHANGELOG_START = "<!-- CHANGELOG:START -->"
CHANGELOG_END = "<!-- CHANGELOG:END -->"

IGNORE_DIR_NAMES = {
    ".git", "node_modules", "dist", "build", ".next", "venv", ".venv",
    "__pycache__", ".pytest_cache", "target", "vendor", ".turbo",
}


def run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()


def get_repo_name() -> str:
    return os.environ.get("REPO_NAME") or os.path.basename(os.getcwd())


def get_commit_message() -> str:
    return run(["git", "log", "-1", "--pretty=%B"]).strip()


def get_diff() -> str:
    # Falls back gracefully on a repo's first commit (no parent to diff against).
    diff = run(["git", "diff", "HEAD~1", "HEAD"])
    if not diff:
        diff = run(["git", "show", "HEAD"])
    if len(diff) > MAX_DIFF_CHARS:
        diff = diff[:MAX_DIFF_CHARS] + "\n... (truncated)"
    return diff


def get_file_tree() -> str:
    entries = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIR_NAMES and not d.startswith(".")]
        for f in files:
            path = os.path.normpath(os.path.join(root, f))
            if path.startswith(".github" + os.sep + "scripts"):
                continue
            entries.append(path)
            if len(entries) >= MAX_TREE_ENTRIES:
                return "\n".join(sorted(entries)) + "\n... (truncated)"
    return "\n".join(sorted(entries))


def read_existing_readme() -> str:
    if os.path.exists(README_PATH):
        with open(README_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def ensure_markers(content: str, repo_name: str) -> str:
    """If a README exists but lacks markers, append scaffolding. If none
    exists, create a minimal starting template."""
    if OVERVIEW_START in content and OVERVIEW_END in content and \
       CHANGELOG_START in content and CHANGELOG_END in content:
        return content

    if not content.strip():
        content = f"# {repo_name}\n\n"

    if OVERVIEW_START not in content:
        content += f"\n## Overview\n\n{OVERVIEW_START}\n{OVERVIEW_END}\n"
    if CHANGELOG_START not in content:
        content += f"\n## Changelog\n\n{CHANGELOG_START}\n{CHANGELOG_END}\n"
    return content


def extract_between(text: str, start: str, end: str) -> str:
    m = re.search(re.escape(start) + r"(.*?)" + re.escape(end), text, re.DOTALL)
    return m.group(1).strip() if m else ""


def replace_between(text: str, start: str, end: str, new_inner: str) -> str:
    pattern = re.escape(start) + r".*?" + re.escape(end)
    replacement = f"{start}\n{new_inner.strip()}\n{end}"
    return re.sub(pattern, lambda _: replacement, text, count=1, flags=re.DOTALL)


def call_claude(system: str, user: str) -> str:
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def build_prompt(repo_name, current_overview, tree, commit_message, diff):
    system = (
        "You maintain a software project's README. You will be given the "
        "current 'Overview' section, a file tree, and the diff of the most "
        "recent commit. Reply with exactly two XML-tagged blocks and nothing "
        "else, no preamble:\n\n"
        "<overview>markdown for the overview section</overview>\n"
        "<changelog_entry>one-line markdown bullet, or empty if this commit "
        "isn't worth a changelog line</changelog_entry>\n\n"
        "Overview rules: plain, factual markdown (no headers, the surrounding "
        "'## Overview' header already exists). Describe what the project is, "
        "how it's structured, and how to use/run it, based on the file tree "
        "and existing content. Preserve accurate details from the current "
        "overview; correct or extend it based on the diff and tree. Keep it "
        "concise — a few short paragraphs or a short list, not exhaustive.\n\n"
        "Changelog rules: one bullet, present tense, plain language, no "
        "conventional-commit jargon. Skip trivial/no-op changes (formatting, "
        "typo fixes, dependency bumps) by returning an empty tag."
    )
    user = (
        f"Repo: {repo_name}\n\n"
        f"## Current overview section\n{current_overview or '(none yet)'}\n\n"
        f"## File tree\n{tree}\n\n"
        f"## Latest commit message\n{commit_message}\n\n"
        f"## Diff\n```diff\n{diff}\n```"
    )
    return system, user


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set — skipping README update.", file=sys.stderr)
        return

    repo_name = get_repo_name()
    content = read_existing_readme()
    content = ensure_markers(content, repo_name)

    current_overview = extract_between(content, OVERVIEW_START, OVERVIEW_END)
    tree = get_file_tree()
    commit_message = get_commit_message()
    diff = get_diff()

    system, user = build_prompt(repo_name, current_overview, tree, commit_message, diff)
    reply = call_claude(system, user)

    overview_match = re.search(r"<overview>(.*?)</overview>", reply, re.DOTALL)
    changelog_match = re.search(r"<changelog_entry>(.*?)</changelog_entry>", reply, re.DOTALL)

    new_overview = overview_match.group(1).strip() if overview_match else current_overview
    new_entry = changelog_match.group(1).strip() if changelog_match else ""

    content = replace_between(content, OVERVIEW_START, OVERVIEW_END, new_overview)

    if new_entry:
        today = date.today().isoformat()
        if not new_entry.startswith("-"):
            new_entry = f"- {new_entry}"
        # Insert the date once, right after the leading "- "
        new_entry = re.sub(r"^-\s*", f"- **{today}** — ", new_entry, count=1)

        existing_changelog = extract_between(content, CHANGELOG_START, CHANGELOG_END)
        lines = [l for l in existing_changelog.splitlines() if l.strip()]
        lines = [new_entry] + lines
        lines = lines[:MAX_CHANGELOG_ENTRIES]
        content = replace_between(content, CHANGELOG_START, CHANGELOG_END, "\n".join(lines))

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")

    print(f"README updated at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
