#!/usr/bin/env bash
# Build Navigator CLI wheel and copy to landing/public/downloads/
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANDING_DIR="$(dirname "$SCRIPT_DIR")"
NAVIGATOR_DIR="$(dirname "$LANDING_DIR")"
DOWNLOADS_DIR="$LANDING_DIR/public/downloads"

cd "$NAVIGATOR_DIR"

echo "Building Navigator CLI..."
python3 -m pip install build -q
python3 -m build --outdir dist

mkdir -p "$DOWNLOADS_DIR"

# Copy wheel (universal py3-none-any works on all platforms)
WHEEL=$(ls dist/navigator-*-py3-none-any.whl 2>/dev/null | head -1)
if [ -n "$WHEEL" ]; then
  cp "$WHEEL" "$DOWNLOADS_DIR/navigator.whl"
  echo "Copied $(basename "$WHEEL") -> downloads/navigator.whl"
fi

# Copy sdist for pip install from source
SDIST=$(ls dist/navigator-*.tar.gz 2>/dev/null | head -1)
if [ -n "$SDIST" ]; then
  cp "$SDIST" "$DOWNLOADS_DIR/"
  echo "Copied $(basename "$SDIST") -> downloads/"
fi

echo "Done. Artifacts in $DOWNLOADS_DIR"
