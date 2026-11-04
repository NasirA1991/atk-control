#!/usr/bin/env bash
# Build a self-contained Flatpak bundle.
#   ./packaging/flatpak/build.sh VERSION [OUTDIR]
# Requires flatpak and flatpak-builder with the GNOME 50 runtime/SDK installed.
set -euo pipefail

version="${1:?usage: build.sh <version> [output-dir]}"
out="${2:-dist}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
mkdir -p "$out"

rm -rf flatpak-build flatpak-repo
flatpak-builder --force-clean --disable-rofiles-fuse \
    --repo=flatpak-repo flatpak-build \
    packaging/flatpak/io.github.compxcontrol.CompxControl.yml

flatpak build-bundle flatpak-repo \
    "$out/compx-control-${version}-x86_64.flatpak" \
    io.github.compxcontrol.CompxControl
echo "built $out/compx-control-${version}-x86_64.flatpak"
