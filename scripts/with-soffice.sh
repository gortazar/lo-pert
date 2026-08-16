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

# A fixed port silently connects the client to whatever office is already listening
# — including a stale one from an earlier run, with a different extension installed.
port="${LO_PERT_PORT:-$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')}"

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

export LO_PERT_PORT="$port"
export LO_PERT_PROFILE="$profile"

# Install the extension into that profile before the office starts — unopkg cannot
# register into a profile an office is already using. LO_PERT_NO_EXTENSION=1 skips
# it, which is what the spikes want.
if [ "${LO_PERT_NO_EXTENSION:-0}" != "1" ]; then
    oxt="$(./build.sh "$profile/build" | tail -1)"
    unopkg add --force "-env:UserInstallation=file://$profile" "$oxt" >/dev/null
fi

# soffice is started *before* URE_BOOTSTRAP is exported. The office bootstraps
# itself from sofficerc; inheriting the fundamentalrc value the python client needs
# makes it abort during startup with a NoSuchElementException, having deleted part
# of the profile it was given.
#
# Deliberately only these switches too: adding --invisible --nodefault --nolockcheck
# is another way to hit that same abort before it ever listens on the socket.
"$soffice_bin" \
    --headless --norestore --nologo \
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

# Now the client environment: program/ holds uno.py and pyuno.so, and pyuno needs
# fundamentalrc to find the type registry.
export PYTHONPATH="$program${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$program${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export URE_BOOTSTRAP="vnd.sun.star.pathname:$program/fundamentalrc"

# soffice reports readiness only by accepting on the socket, so poll it.
for _ in $(seq 1 120); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
        exec 3<&- 3>&-
        break
    fi
    sleep 0.5
done

"$@"
