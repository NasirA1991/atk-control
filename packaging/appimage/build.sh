#!/usr/bin/env bash
# Build a lean AppImage.  The host provides GTK4/PyGObject.
#   ./packaging/appimage/build.sh VERSION [OUTDIR]
set -euo pipefail

version="${1:?usage: build.sh <version> [output-dir]}"
out="${2:-dist}"
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
mkdir -p "$out"

rm -rf AppDir
mkdir -p AppDir/usr/share/atk-control
cp -r atk_control data AppDir/usr/share/atk-control/
find AppDir/usr/share/atk-control -name '__pycache__' -type d -prune -exec rm -rf {} +
install -Dm755 packaging/appimage/AppRun AppDir/AppRun
install -Dm644 packaging/appimage/launcher.py AppDir/usr/share/atk-control/launcher.py
install -Dm644 data/icons/atk-control.png AppDir/atk-control.png
install -Dm644 data/icons/hicolor/scalable/apps/atk-control.svg AppDir/atk-control.svg
install -Dm644 data/applications/io.github.atkcontrol.AtkControl.desktop AppDir/atk-control.desktop
install -Dm644 data/applications/io.github.atkcontrol.AtkControl.desktop \
    AppDir/usr/share/applications/atk-control.desktop
install -Dm644 data/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml \
    AppDir/usr/share/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml
chmod -R a+rX AppDir

tool="${APPIMAGETOOL:-/tmp/appimagetool-1.9.1-x86_64.AppImage}"
if [[ -z "${APPIMAGETOOL:-}" ]]; then
    tool_version="1.9.1"
    sha256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
    if [[ ! -x "$tool" ]] || ! printf '%s  %s\n' "$sha256" "$tool" | sha256sum -c - >/dev/null 2>&1; then
        curl -fsSL "https://github.com/AppImage/appimagetool/releases/download/${tool_version}/appimagetool-x86_64.AppImage" -o "$tool"
        chmod +x "$tool"
    fi
    printf '%s  %s\n' "$sha256" "$tool" | sha256sum -c -
fi

ARCH=x86_64 "$tool" --appimage-extract-and-run "AppDir" \
    "$out/atk-control-${version}-x86_64.AppImage"
echo "built $out/atk-control-${version}-x86_64.AppImage"
