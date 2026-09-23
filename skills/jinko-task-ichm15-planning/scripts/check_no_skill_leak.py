#!/usr/bin/env python3
"""Fail if internal skill/implementation names leak into a generated deliverable.

The ICH M15 planning outputs (assessment table, MAP document, Jinko documents)
are regulator-facing. Names of the skills, files, or tooling used to produce
them have no meaning to a reviewer and must never appear in the deliverable.

Usage:
    python check_no_skill_leak.py <file1.md> [file2.md ...]

Exits 1 and prints every offending line if a leak is found, 0 otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Matches any jinko-* / nova-* skill-style identifier (e.g. jinko-document,
# jinko-task-ichm15-planning, nova-workflow-model-plan). Deliberately generic
# rather than an enumerated skill list, so it still catches a skill renamed or
# added after this check was written.
SKILL_NAME_PATTERN = re.compile(
    r"\b(?:jinko|nova)-[a-z0-9]+(?:-[a-z0-9]+)*\b", re.IGNORECASE
)

# Literal internal-implementation terms that should never reach the reader.
LITERAL_TERMS = [
    "SKILL.md",
    "skill name",
    "this skill",
    ".agents/skills",
    ".claude/skills",
    "references/map.md",
    "references/terms.md",
]


def find_leaks(text: str) -> list[tuple[int, str, str]]:
    leaks = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in SKILL_NAME_PATTERN.finditer(line):
            leaks.append((lineno, match.group(0), line.strip()))
        for term in LITERAL_TERMS:
            if term.lower() in line.lower():
                leaks.append((lineno, term, line.strip()))
    return leaks


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: check_no_skill_leak.py <file1.md> [file2.md ...]", file=sys.stderr
        )
        return 2

    all_leaks: list[tuple[str, int, str, str]] = []
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            print(f"error: no such file: {path}", file=sys.stderr)
            return 2
        text = path.read_text(encoding="utf-8")
        for lineno, token, line in find_leaks(text):
            all_leaks.append((str(path), lineno, token, line))

    if all_leaks:
        print("Internal implementation references found — remove before delivering:\n")
        for path, lineno, token, line in all_leaks:
            print(f"  {path}:{lineno}: matched '{token}'")
            print(f"    {line}")
        return 1

    print(f"OK: no internal skill/implementation references in {len(argv)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
