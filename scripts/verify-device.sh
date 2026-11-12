#!/usr/bin/env bash
# Read-only verification for one ATK/VXE mouse.
#
# Runs the read-only path (scan, status, capabilities, battery) and saves a
# sanitized support report that can be attached to a device-support issue.
# It never writes to the mouse: every setting is only read.
#
#   ./scripts/verify-device.sh                  # verify the first mouse found
#   ./scripts/verify-device.sh -d /dev/hidraw3  # pick a specific interface
#   ./scripts/verify-device.sh -o ~/atk-tests   # choose where the report goes
#   ./scripts/verify-device.sh --raw            # include raw registers
#
# Exit codes: 0 = a mouse answered, 1 = attention needed (see the notes),
# 2 = no supported ATK/VXE interface was found, 3 = setup problem.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="."
DEVICE=""
INCLUDE_RAW=0
WRITE_REPORT=1
FAILURES=0

usage() {
    cat <<'EOF'
Usage: ./scripts/verify-device.sh [options]

  -d, --device PATH   hidraw node to use (default: the first supported one)
  -o, --output DIR    directory for the saved report (default: current dir)
      --raw           include the raw register window in the report
      --no-report     skip writing the report file
  -h, --help          show this help

The script only reads. Close ATK Control and any `atkctl watch` first: the app
takes a per-device lock, so two writers cannot share one mouse.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -d|--device) DEVICE="${2:?missing device path}"; shift 2 ;;
        -o|--output) OUTPUT_DIR="${2:?missing output directory}"; shift 2 ;;
        --raw) INCLUDE_RAW=1; shift ;;
        --no-report) WRITE_REPORT=0; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 3 ;;
    esac
done

section() {
    printf '\n== %s ==\n' "$1"
}

note() {
    printf '   %s\n' "$1"
}

# Prefer the checkout wrapper so the script tests the working tree, then an
# installed `atkctl`, then the wrapper through python3 from any directory.
if [ -n "${ATKCTL:-}" ]; then
    CLI=("$ATKCTL")
elif [ -x "$ROOT/atkctl" ]; then
    CLI=("$ROOT/atkctl")
elif command -v atkctl >/dev/null 2>&1; then
    CLI=(atkctl)
elif command -v python3 >/dev/null 2>&1 && [ -f "$ROOT/atkctl" ]; then
    CLI=(python3 "$ROOT/atkctl")
else
    echo "atkctl was not found. Run this from the repository checkout, install" >&2
    echo "ATK Control (AUR or ./install.sh), or set ATKCTL=/path/to/atkctl." >&2
    exit 3
fi

section "Environment"
date -Is 2>/dev/null || true
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    note "distribution: ${PRETTY_NAME:-unknown}"
else
    note "distribution: unknown"
fi
note "kernel: $(uname -srm)"
note "shell: ${BASH_VERSION:-unknown}"
if command -v python3 >/dev/null 2>&1; then
    note "python: $(python3 -V 2>&1)"
else
    note "python: not found"
fi
note "cli: ${CLI[*]}"
note "version: $("${CLI[@]}" --version 2>&1 || echo unknown)"
if [ -n "${FLATPAK_ID:-}" ]; then
    note "session: Flatpak sandbox (${FLATPAK_ID})"
elif [ -n "${container:-}" ]; then
    note "session: container (${container})"
else
    note "session: native"
fi
note "user: $(id -un); groups: $(id -Gn 2>/dev/null || echo unknown)"
RULE_FOUND=""
for rule in /usr/lib/udev/rules.d/71-atk-control.rules \
            /etc/udev/rules.d/71-atk-control.rules; do
    if [ -f "$rule" ]; then
        RULE_FOUND="$rule"
        break
    fi
done
if [ -n "$RULE_FOUND" ]; then
    note "udev rule: $RULE_FOUND"
else
    note "udev rule: not installed (the CLI then needs root)"
fi

section "Configuration interfaces"
SCAN_OUTPUT="$("${CLI[@]}" scan --all 2>&1)" || true
printf '%s\n' "$SCAN_OUTPUT"

# Keep the interfaces the app considers supported; "unsupported:" lines only
# describe a diagnostic descriptor.
SUPPORTED_NODES="$(printf '%s\n' "$SCAN_OUTPUT" \
    | grep -v 'unsupported:' \
    | grep -E '^/dev/' \
    | awk '{print $1}' || true)"

if [ -z "$SUPPORTED_NODES" ]; then
    FAILURES=1
    note "no supported ATK/VXE configuration interface was found."
    note "the saved report is a discovery report, which is what a maintainer"
    note "needs to add the model."
fi

section "Permissions"
if [ -n "$SUPPORTED_NODES" ]; then
    # Word splitting is intended: one node per line.
    # shellcheck disable=SC2086
    for node in $SUPPORTED_NODES; do
        if [ -e "$node" ]; then
            note "$(ls -l "$node" 2>/dev/null || echo "$node: cannot stat")"
            if [ -r "$node" ] && [ -w "$node" ]; then
                note "$node: readable and writable by $(id -un)"
            else
                note "$node: NOT writable by $(id -un)"
                note "install the udev rule (data/udev/71-atk-control.rules in the"
                note "checkout) and reconnect the mouse, or run the CLI as root."
            fi
        else
            note "$node: missing"
        fi
    done
else
    note "nothing to check"
fi

DEVICE_ARGS=()
if [ -n "$DEVICE" ]; then
    DEVICE_ARGS=(--device "$DEVICE")
fi

section "Status (read-only)"
if STATUS_OUTPUT="$("${CLI[@]}" "${DEVICE_ARGS[@]}" status 2>&1)"; then
    printf '%s\n' "$STATUS_OUTPUT"
else
    printf '%s\n' "$STATUS_OUTPUT"
    FAILURES=1
    note "status failed: the mouse did not answer. Turn it on and move it, then"
    note "retry. Over a receiver the paired mouse has to be awake."
fi

section "Capabilities (read-only)"
if CAPS_OUTPUT="$("${CLI[@]}" "${DEVICE_ARGS[@]}" caps 2>&1)"; then
    printf '%s\n' "$CAPS_OUTPUT"
else
    printf '%s\n' "$CAPS_OUTPUT"
    FAILURES=$((FAILURES + 1))
fi

section "Battery (read-only)"
BATTERY_OUTPUT="$("${CLI[@]}" "${DEVICE_ARGS[@]}" battery 2>&1)" || true
printf '%s\n' "$BATTERY_OUTPUT"

REPORT_PATH=""
if [ "$WRITE_REPORT" -eq 1 ]; then
    section "Saved report"
    mkdir -p "$OUTPUT_DIR"
    STAMP="$(date +%Y%m%d-%H%M%S 2>/dev/null || echo report)"
    REPORT_PATH="$OUTPUT_DIR/atk-verify-${STAMP}.md"
    REPORT_ARGS=(-o "$REPORT_PATH")
    if [ "$INCLUDE_RAW" -eq 1 ]; then
        REPORT_ARGS=(--raw "${REPORT_ARGS[@]}")
    fi
    if "${CLI[@]}" "${DEVICE_ARGS[@]}" support "${REPORT_ARGS[@]}"; then
        if [ -f "$REPORT_PATH" ]; then
            note "saved: $REPORT_PATH"
            note "review it, then attach it to the device-support issue."
        else
            note "the CLI reported success but $REPORT_PATH is missing"
            FAILURES=$((FAILURES + 1))
        fi
    else
        note "the report could not be written"
        FAILURES=$((FAILURES + 1))
    fi
fi

section "Summary"
note "read-only run: no setting on the mouse was changed"
if [ -n "$SUPPORTED_NODES" ]; then
    # shellcheck disable=SC2086
    note "supported interfaces: $(printf '%s' "$SUPPORTED_NODES" | tr '\n' ' ')"
else
    note "supported interfaces: none"
fi
if [ -n "$REPORT_PATH" ] && [ -f "$REPORT_PATH" ]; then
    note "attach: $REPORT_PATH"
fi
if [ -z "$SUPPORTED_NODES" ] && [ -z "$DEVICE" ]; then
    note "result: no supported interface (see the discovery report above)"
    exit 2
fi
if [ "$FAILURES" -eq 0 ]; then
    note "result: OK"
    exit 0
fi
note "result: attention needed (see the notes above)"
exit 1
