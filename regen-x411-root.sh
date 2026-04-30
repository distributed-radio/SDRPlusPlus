#!/usr/bin/env bash
# Regenerate a portable SDR++ root dir pointing at this repo's build-x411 tree.
# No sudo, no system install. Survives reboots if $ROOT lives outside /tmp.
#
# Usage: ./regen-x411-root.sh [ROOT]    (default: /tmp/sdrpp_x411_test)
set -e
cd "$(dirname "$0")"
REPO="$(pwd)"
ROOT="${1:-/tmp/sdrpp_x411_test}"
BUILD="$REPO/build-x411"

[ -d "$BUILD" ] || { echo "build-x411 not found — run ./build-x411.sh first" >&2; exit 1; }

mkdir -p "$ROOT" "$ROOT/modules"
rm -rf "$ROOT/res"
cp -r "$REPO/root/res" "$ROOT/res"

MODULES_JSON=$(find "$BUILD" -name "*.so" -not -name "libsdrpp_core.so" -not -name "libcorrect.so" \
    | sort | jq -R . | jq -s .)

CFG="$ROOT/config.json"
X411_INSTANCE='{"enabled": true, "module": "x411_source"}'
if [ -f "$CFG" ]; then
    TMP=$(mktemp)
    jq --argjson mods "$MODULES_JSON" --arg mdir "$ROOT/modules" --arg res "$ROOT/res" \
       --argjson x411 "$X411_INSTANCE" \
        '.modules = $mods | .modulesDirectory = $mdir | .resourcesDirectory = $res
         | .moduleInstances["X411 Source"] = $x411' \
        "$CFG" > "$TMP" && mv "$TMP" "$CFG"
else
    jq -n --argjson mods "$MODULES_JSON" --arg mdir "$ROOT/modules" --arg res "$ROOT/res" \
          --argjson x411 "$X411_INSTANCE" \
        '{modules: $mods, modulesDirectory: $mdir, resourcesDirectory: $res,
          moduleInstances: {"X411 Source": $x411}}' > "$CFG"
fi

echo "Regenerated $ROOT"
echo "  res  : $ROOT/res"
echo "  cfg  : $CFG ($(echo "$MODULES_JSON" | jq length) modules)"
echo ""
echo "Run with: ./run-x411.sh $ROOT     (or ./run-x411-debug.sh $ROOT)"
