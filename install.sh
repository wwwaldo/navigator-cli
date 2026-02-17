#!/usr/bin/env bash
# Install Navigator — https://github.com/.../navigator

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install Python 3.10+ from python.org"
    exit 1
fi

python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null || {
    echo "Warning: Python 3.10+ required. Check with: python3 --version"
}

# Install
echo "Installing Navigator..."
pip install -e .

# Verify
if command -v navigator &>/dev/null; then
    echo ""
    echo "✓ Navigator installed. Run: navigator --help"
    echo ""
    echo "Next steps:"
    echo "  • Cloud: navigator config --api-key sk-ant-...  (from console.anthropic.com)"
    echo "  • Local: Install Ollama from ollama.com, then navigator model pull llama3.2"
else
    echo "Install may have succeeded but 'navigator' not in PATH. Try: pip install -e ."
    exit 1
fi
