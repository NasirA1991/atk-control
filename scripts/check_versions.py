#!/usr/bin/env python3
"""Fail if any shipped version source disagrees with config.VERSION."""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def _search(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise SystemExit(f"could not find version in {path}")
    return match.group(1)


def versions() -> dict[str, str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    metainfo = ET.parse(ROOT / "data/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml")
    release = metainfo.find("./releases/release")
    if release is None or not release.get("version"):
        raise SystemExit("could not find the first release in metainfo.xml")
    return {
        "config.py": _search("atk_control/config.py", r'^VERSION = "([^"]+)"'),
        "pyproject.toml": str(pyproject["project"]["version"]),
        "PKGBUILD": _search("PKGBUILD", r"^pkgver=([^\s]+)"),
        "atk-control-git/PKGBUILD.in": _search(
            "packaging/aur/atk-control-git/PKGBUILD.in", r"^pkgver=([^\s]+)"
        ),
        "metainfo.xml": release.get("version", ""),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="release tag such as v0.5.3")
    args = parser.parse_args(argv)
    found = versions()
    unique = set(found.values())
    if len(unique) != 1:
        for name, value in found.items():
            print(f"{name:32} {value}", file=sys.stderr)
        print("version sources disagree", file=sys.stderr)
        return 1
    version = unique.pop()
    if args.tag and args.tag.removeprefix("v") != version:
        print(f"tag {args.tag} does not match VERSION {version}", file=sys.stderr)
        return 1
    print(f"version sources agree: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
