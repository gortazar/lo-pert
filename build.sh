#!/usr/bin/env bash
# Build dist/lo-pert-<version>.oxt.
#
# An .oxt is a zip of oxt/ with two additions: the version from VERSION
# substituted into description.xml, and src/lopert copied to pythonpath/lopert —
# LibreOffice's python loader puts an extension's pythonpath/ on sys.path, which is
# what makes `from lopert import commands` work inside the office.
#
#     ./build.sh [output-directory]     # default: dist/
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

version="$(tr -d '\n' < VERSION)"
out_dir="${1:-$PWD/dist}"
oxt="$out_dir/lo-pert-$version.oxt"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

cp -r oxt/. "$stage/"
sed -i "s/@VERSION@/$version/g" "$stage/description.xml"

mkdir -p "$stage/pythonpath"
cp -r src/lopert "$stage/pythonpath/lopert"
# .pyc from a local test run would ship a stale copy of the code.
find "$stage" -name '__pycache__' -type d -prune -exec rm -rf {} +

# The version the About box reports comes from the same file as the tag.
sed -i "s/^VERSION = .*/VERSION = \"$version\"/" "$stage/pythonpath/lopert/commands.py"

grep -q '@VERSION@' "$stage/description.xml" && {
    echo "description.xml still has an unsubstituted @VERSION@" >&2
    exit 1
}

mkdir -p "$out_dir"
rm -f "$oxt"
# mimetype-style ordering does not matter for .oxt, but a deterministic archive
# does: -X drops extra file attributes, and sorted input keeps the entry order
# stable between builds.
( cd "$stage" && find . -type f | LC_ALL=C sort | zip -qX "$oxt" -@ )

echo "$oxt"
