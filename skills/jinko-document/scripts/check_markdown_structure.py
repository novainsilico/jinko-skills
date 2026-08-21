#!/usr/bin/env python3
"""Reject deterministic structural losses between approved Markdown payloads."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\([^)]+\)")
REFERENCE_MARKER = "<!-- jinko:references -->"


def normalized_row(line: str) -> str:
    return "|".join(cell.strip() for cell in line.strip().strip("|").split("|"))


def section_line_counts(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    active_sections: list[tuple[int, str]] = []
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            name = match.group(2).strip().casefold()
            active_sections = [
                section for section in active_sections if section[0] < level
            ]
            active_sections.append((level, name))
            counts.setdefault(name, 0)
            continue
        if line.strip():
            for _, name in active_sections:
                counts[name] += 1
    return counts


def section_contents(lines: list[str]) -> dict[str, list[str]]:
    contents: dict[str, list[str]] = {}
    active_sections: list[tuple[int, str]] = []
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            for active_level, name in active_sections:
                if active_level < level:
                    contents[name].append(line.rstrip())
            active_sections = [
                section for section in active_sections if section[0] < level
            ]
            name = match.group(2).strip().casefold()
            active_sections.append((level, name))
            contents.setdefault(name, [])
            continue
        if line.strip():
            for _, name in active_sections:
                contents[name].append(line.rstrip())
    return contents


def without_generated_references(lines: list[str], enabled: bool) -> list[str]:
    if not enabled:
        return lines
    result: list[str] = []
    ignored_level: int | None = None
    marker_seen = False
    for line in lines:
        if line.strip() == REFERENCE_MARKER:
            marker_seen = True
            continue
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            if ignored_level is not None and level <= ignored_level:
                ignored_level = None
            if marker_seen and match.group(2).strip().casefold() == "references":
                ignored_level = level
                marker_seen = False
                continue
            marker_seen = False
        elif marker_seen:
            marker_seen = False
        if ignored_level is None:
            result.append(line)
    return result


def inspect_markdown(
    path: Path, *, ignore_generated_references: bool = False
) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = without_generated_references(text.splitlines(), ignore_generated_references)
    text = "\n".join(lines)
    headings = Counter(
        match.group(2).strip().casefold()
        for line in lines
        if (match := HEADING_RE.match(line))
    )
    tables: Counter[str] = Counter()
    index = 0
    while index + 1 < len(lines):
        if "|" in lines[index] and TABLE_SEPARATOR_RE.match(lines[index + 1]):
            header = normalized_row(lines[index]).casefold()
            row_count = 0
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                row_count += 1
                index += 1
            tables[header] += row_count
            continue
        index += 1

    math_blocks = len(re.findall(r"^```mathBlock\s*$", text, flags=re.MULTILINE))
    inline_math = sum(
        len(re.findall(r"(?<!\\)\$(?!\$)[^\n$]+(?<!\\)\$", line))
        for line in lines
        if not line.startswith("```")
    )
    return {
        "headings": dict(sorted(headings.items())),
        "table_rows_by_header": dict(sorted(tables.items())),
        "math_blocks": math_blocks,
        "inline_math": inline_math,
        "links": len(LINK_RE.findall(text)),
        "section_lines": section_line_counts(lines),
        "section_contents": section_contents(lines),
    }


def structural_losses(
    baseline: dict[str, object],
    candidate: dict[str, object],
    append_only_sections: list[str],
) -> list[str]:
    losses: list[str] = []
    for field in ("headings", "table_rows_by_header"):
        old_values = baseline[field]
        new_values = candidate[field]
        assert isinstance(old_values, dict) and isinstance(new_values, dict)
        for key, old_count in old_values.items():
            new_count = new_values.get(key, 0)
            if new_count < old_count:
                losses.append(f"{field}[{key!r}] decreased: {old_count} -> {new_count}")

    for field in ("math_blocks", "inline_math", "links"):
        old_count = baseline[field]
        new_count = candidate[field]
        assert isinstance(old_count, int) and isinstance(new_count, int)
        if new_count < old_count:
            losses.append(f"{field} decreased: {old_count} -> {new_count}")

    for raw_name in append_only_sections:
        name = raw_name.strip().casefold()
        old_contents = baseline["section_contents"]
        new_contents = candidate["section_contents"]
        assert isinstance(old_contents, dict) and isinstance(new_contents, dict)
        old_content = old_contents.get(name, [])
        new_content = new_contents.get(name, [])
        if new_content[: len(old_content)] != old_content:
            losses.append(
                f"append-only section {raw_name!r} changed or removed existing content"
            )
    return losses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument(
        "--append-only-section",
        action="append",
        default=[],
        help="Heading whose existing non-empty content must remain an exact prefix",
    )
    args = parser.parse_args()

    baseline = inspect_markdown(Path(args.baseline))
    candidate = inspect_markdown(Path(args.candidate))
    losses = structural_losses(baseline, candidate, args.append_only_section)
    print(
        json.dumps(
            {"baseline": baseline, "candidate": candidate, "losses": losses},
            sort_keys=True,
        )
    )
    return 1 if losses else 0


if __name__ == "__main__":
    raise SystemExit(main())
