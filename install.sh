#!/usr/bin/env sh
# Install lo-pert into your LibreOffice.
#
#     curl -fsSL https://raw.githubusercontent.com/gortazar/lo-pert/main/install.sh | sh
#
# Downloads the .oxt from the latest GitHub release, checks it against the published
# SHA256SUMS, and registers it with unopkg. Nothing is compiled and nothing outside
# LibreOffice's own extension directory is touched.
#
# LO_PERT_VERSION=v0.2 installs a specific release instead of the latest one.
set -eu

REPO="gortazar/lo-pert"
VERSION="${LO_PERT_VERSION:-latest}"

say() { printf '%s\n' "$*"; }
die() { printf 'lo-pert: %s\n' "$*" >&2; exit 1; }

need() {
    command -v "$1" >/dev/null 2>&1 || die "this installer needs $1 on PATH"
}

find_unopkg() {
    if command -v unopkg >/dev/null 2>&1; then
        command -v unopkg
        return
    fi
    # The usual places a distribution or the LibreOffice .deb puts it.
    for candidate in \
        /usr/lib/libreoffice/program/unopkg \
        /usr/lib64/libreoffice/program/unopkg \
        /opt/libreoffice*/program/unopkg \
        /snap/libreoffice/current/lib/libreoffice/program/unopkg \
        "/Applications/LibreOffice.app/Contents/MacOS/unopkg"
    do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return
        fi
    done
    die "cannot find unopkg — is LibreOffice installed?"
}

need curl
UNOPKG="$(find_unopkg)"

if [ "$VERSION" = "latest" ]; then
    base="https://github.com/$REPO/releases/latest/download"
else
    base="https://github.com/$REPO/releases/download/$VERSION"
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT INT TERM

say "lo-pert: downloading the extension..."
# The release always carries these two names; SHA256SUMS then says which .oxt
# filename (and therefore which version) they belong to.
curl -fsSL "$base/SHA256SUMS" -o "$work/SHA256SUMS" \
    || die "no release found at $base"
asset="$(awk '{ print $2 }' "$work/SHA256SUMS" | sed 's/^\*//' | head -1)"
[ -n "$asset" ] || die "the release's SHA256SUMS names no .oxt"
curl -fsSL "$base/$asset" -o "$work/$asset" || die "could not download $asset"

if command -v sha256sum >/dev/null 2>&1; then
    ( cd "$work" && sha256sum -c SHA256SUMS >/dev/null ) \
        || die "the downloaded $asset does not match its published checksum"
elif command -v shasum >/dev/null 2>&1; then
    ( cd "$work" && shasum -a 256 -c SHA256SUMS >/dev/null ) \
        || die "the downloaded $asset does not match its published checksum"
else
    say "lo-pert: no sha256sum available, skipping the checksum check"
fi

say "lo-pert: installing $asset with unopkg..."
# --force replaces an older lo-pert rather than refusing to install over it.
"$UNOPKG" add --force "$work/$asset" \
    || die "unopkg refused the extension (close LibreOffice and try again)"

say "lo-pert: installed. Open Draw, Impress or Calc and look for the PERT menu."
