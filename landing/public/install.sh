#!/usr/bin/env sh
# Install Navigator — https://getnavigator.app
# Usage: curl -fsSL https://getnavigator.app/install.sh | sh

set -e

BASE_URL="${NAVIGATOR_INSTALL_URL:-https://getnavigator.app}"
WHEEL_FILE=$(curl -fsSL "$BASE_URL/downloads/latest.txt" 2>/dev/null | tr -d '\r\n' | grep -E '^navigator-[0-9.]+-py3-none-any\.whl$' | head -1)
WHEEL_FILE="${WHEEL_FILE:-navigator-0.1.0-py3-none-any.whl}"
WHEEL_URL="$BASE_URL/downloads/$WHEEL_FILE"

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ from python.org"
  exit 1
fi

python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || {
  echo "Warning: Python 3.10+ required. Check with: python3 --version"
}

echo "Installing Navigator..."
TMP_DIR=$(mktemp -d 2>/dev/null || mktemp -d -t navigator)
trap 'rm -rf "$TMP_DIR"' EXIT
TMP_WHL="$TMP_DIR/$WHEEL_FILE"
if ! curl -fsSL "$WHEEL_URL" -o "$TMP_WHL"; then
  echo "Error: Failed to download Navigator. Check your connection and try again."
  exit 1
fi
if ! head -c 2 "$TMP_WHL" | grep -q '^PK'; then
  echo "Error: Downloaded file is not a valid wheel (server may have returned an error page)."
  echo "Try: pip install $WHEEL_URL"
  exit 1
fi
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
