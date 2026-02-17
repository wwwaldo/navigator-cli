#!/usr/bin/env sh
# Install Navigator — https://getnavigator.app
# Usage: curl -fsSL https://getnavigator.app/install.sh | sh

set -e

BASE_URL="${NAVIGATOR_INSTALL_URL:-https://getnavigator.app}"
WHEEL_URL="$BASE_URL/downloads/navigator.whl"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ from python.org"
  exit 1
fi

python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || {
  echo "Warning: Python 3.10+ required. Check with: python3 --version"
}

echo "Installing Navigator..."
TMP_WHL="${TMPDIR:-/tmp}/navigator-install-$$.whl"
trap 'rm -f "$TMP_WHL"' EXIT

curl -fsSL "$WHEEL_URL" -o "$TMP_WHL"
python3 -m pip install --quiet "$TMP_WHL"

if command -v navigator >/dev/null 2>&1; then
  echo ""
  echo "✓ Navigator installed. Run: navigator --help"
  echo ""
  echo "Next steps:"
  echo "  • Cloud: navigator config --api-key sk-ant-...  (from console.anthropic.com)"
  echo "  • Local: Install Ollama from ollama.com, then navigator model pull llama3.2"
else
  echo "Install may have succeeded but 'navigator' not in PATH."
  echo "Try: python3 -m pip install $WHEEL_URL"
  exit 1
fi
