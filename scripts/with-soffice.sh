#!/usr/bin/env bash
# Run a command against a throwaway headless LibreOffice.
#
# Starts soffice with a fresh user profile listening on a UNO socket, exports the
# variables PyUNO needs to bootstrap (nixpkgs' libreoffice ships pyuno.so linked
# against the same python3 as the dev shell, so plain `import uno` works once
# PYTHONPATH, LD_LIBRARY_PATH and URE_BOOTSTRAP point at program/), runs the
# command, then shuts the office down.
#
#     ./scripts/with-soffice.sh python3 spikes/connector_glue.py
#
# LO_PERT_PORT overrides the port; LO_PERT_PROFILE keeps the profile directory
# afterwards (that is how the .oxt under test gets installed into it).
set -euo pipefail

port="${LO_PERT_PORT:-2002}"

soffice_bin="${SOFFICE:-soffice}"
command -v "$soffice_bin" >/dev/null || {
    echo "no soffice on PATH — run inside 'nix develop'" >&2
    exit 1
}

# program/ holds uno.py, pyuno.so and the bootstrap rc files. Resolve it from the
# binary so this works for any LibreOffice, nix-installed or not.
soffice_real="$(readlink -f "$(command -v "$soffice_bin")")"
program="$(dirname "$soffice_real")"
[ -f "$program/uno.py" ] || program="$(dirname "$program")/lib/libreoffice/program"
[ -f "$program/uno.py" ] || {
    echo "cannot find LibreOffice program/ directory (looked near $soffice_real)" >&2
    exit 1
}

profile="${LO_PERT_PROFILE:-}"
cleanup_profile=0
if [ -z "$profile" ]; then
    profile="$(mktemp -d)"
    cleanup_profile=1
fi
mkdir -p "$profile"

export PYTHONPATH="$program${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$program${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export URE_BOOTSTRAP="vnd.sun.star.pathname:$program/fundamentalrc"
export LO_PERT_PORT="$port"
export LO_PERT_PROFILE="$profile"

"$soffice_bin" \
    --headless --invisible --norestore --nologo --nodefault --nolockcheck \
    "-env:UserInstallation=file://$profile" \
    "--accept=socket,host=127.0.0.1,port=$port;urp;StarOffice.ServiceManager" &
soffice_pid=$!

shutdown() {
    status=$?
    kill "$soffice_pid" 2>/dev/null || true
    wait "$soffice_pid" 2>/dev/null || true
    [ "$cleanup_profile" = 1 ] && rm -rf "$profile"
    exit "$status"
}
trap shutdown EXIT INT TERM

# soffice reports readiness only by accepting on the socket, so poll it.
for _ in $(seq 1 120); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        exec 3<&- 3>&-
        break
    fi
    sleep 0.5
done

"$@"
