#!/usr/bin/env python3
"""Validate documentation links, anchors and pinned download versions."""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
VERSION_RE = re.compile(r"atk-control-(\d+\.\d+\.\d+)-x86_64")
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)


def slug(text: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def anchors(path: Path) -> set[str]:
    return {slug(match.group(2)) for match in HEADING_RE.finditer(path.read_text(encoding="utf-8"))}


def source_version() -> str:
    match = re.search(
        r'^VERSION = "([^"]+)"',
        (ROOT / "atk_control/config.py").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if match is None:
        raise SystemExit("could not read VERSION from atk_control/config.py")
    return match.group(1)


def main() -> int:
    version = source_version()
    problems: list[str] = []
    checked_links = 0
    checked_versions = 0

    for doc in DOCS:
        if not doc.exists():
            problems.append(f"{doc.relative_to(ROOT)}: file is missing")
            continue
        text = doc.read_text(encoding="utf-8")
        doc_anchors = anchors(doc)
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            checked_links += 1
            if target.startswith("#"):
                if target[1:] not in doc_anchors:
                    problems.append(f"{doc.relative_to(ROOT)}: missing anchor {target}")
                continue
            relative, _, fragment = target.partition("#")
            target_path = (doc.parent / relative).resolve()
            if not target_path.exists():
                problems.append(f"{doc.relative_to(ROOT)}: missing path {relative}")
                continue
            if fragment:
                if target_path.suffix != ".md":
                    problems.append(f"{doc.relative_to(ROOT)}: anchor on non-Markdown {target}")
                elif fragment not in anchors(target_path):
                    problems.append(f"{doc.relative_to(ROOT)}: missing anchor {target}")

        for match in VERSION_RE.finditer(text):
            checked_versions += 1
            if match.group(1) != version:
                problems.append(
                    f"{doc.relative_to(ROOT)}: pinned {match.group(0)} "
                    f"does not match VERSION {version}"
                )

    if checked_versions == 0:
        problems.append("no versioned download filenames found")

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"documentation check failed with {len(problems)} problem(s)", file=sys.stderr)
        return 1

    print(
        f"documentation checks passed: {len(DOCS)} files, "
        f"{checked_links} local links, {checked_versions} version references"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
