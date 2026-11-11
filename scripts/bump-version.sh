#!/usr/bin/env bash
# Update every versioned file from one version argument.
set -euo pipefail
version="${1:?usage: bump-version.sh X.Y.Z}"
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

sed -i -E "s/^VERSION = \"[^\"]+\"/VERSION = \"${version}\"/" atk_control/config.py
sed -i -E "s/^version = \"[^\"]+\"/version = \"${version}\"/" pyproject.toml
sed -i -E "s/^pkgver=.*/pkgver=${version}/" PKGBUILD
sed -i -E "0,/pkgver=0\.[0-9]+\.[0-9]+/s//pkgver=${version}/" packaging/aur/atk-control-git/PKGBUILD.in
sed -i -E "s/<release version=\"[^\"]+\"/<release version=\"${version}\"/" \
    data/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml
sed -i -E "s/atk-control-[0-9]+\.[0-9]+\.[0-9]+-x86_64/atk-control-${version}-x86_64/g" \
    README.md docs/INSTALLATION.md docs/TROUBLESHOOTING.md
echo "Bumped to ${version}. Add a metainfo release entry and commit."
