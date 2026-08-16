#!/usr/bin/env bash
# Install the *published* release the way a user would, then check it works.
#
#     ./scripts/verify-release.sh [version]      # default: latest
#
# Runs install.sh from a clean directory with a throwaway HOME, so the extension
# lands in a fresh LibreOffice profile and nothing on this machine is touched. Then
# starts that office and drives the generate command through the installed
# extension: an installer that was never executed is a guess, and an .oxt that
# installs but contributes no menu looks exactly like a working one until then.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

version="${1:-latest}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT INT TERM

export HOME="$work/home"
mkdir -p "$HOME" "$work/clean"

echo "== installing $version into a clean profile =="
cd "$work/clean"
curl -fsSL https://raw.githubusercontent.com/gortazar/lo-pert/main/install.sh -o install.sh
if [ "$version" = "latest" ]; then
    sh install.sh
else
    LO_PERT_VERSION="$version" sh install.sh
fi

# Captured rather than piped into grep: under `set -o pipefail`, grep -q exits at
# the first match and unopkg dies of SIGPIPE, failing the check that just passed.
installed="$(unopkg list)"
case "$installed" in
    *com.github.gortazar.lopert*) ;;
    *)
        echo "the extension is not registered after install.sh" >&2
        exit 1
        ;;
esac

echo "== driving the installed extension =="
cd - >/dev/null
port="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
soffice --headless --norestore --nologo \
    "--accept=socket,host=127.0.0.1,port=$port;urp;StarOffice.ServiceManager" &
office=$!
trap 'kill "$office" 2>/dev/null || true; rm -rf "$work"' EXIT INT TERM

program="$(dirname "$(readlink -f "$(command -v soffice)")")"
export PYTHONPATH="$program${PYTHONPATH:+:$PYTHONPATH}"
export URE_BOOTSTRAP="vnd.sun.star.pathname:$program/fundamentalrc"
for _ in $(seq 1 120); do
    (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null && { exec 3<&- 3>&-; break; }
    sleep 0.5
done

LO_PERT_PORT="$port" python3 scripts/verify_release.py
echo "== the published release installs and draws =="
