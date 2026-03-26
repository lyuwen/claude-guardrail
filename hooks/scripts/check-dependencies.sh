#!/usr/bin/env bash
set -euo pipefail

echo "Checking Python dependencies..."

# Check Python version
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install Python 3.10 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_VERSION="3.10"

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    echo "❌ Python $PYTHON_VERSION found, but 3.10+ required."
    exit 1
fi

echo "✓ Python $PYTHON_VERSION"

# Check PyYAML
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "❌ PyYAML not installed."
    echo "   Install with: pip install pyyaml"
    exit 1
fi

echo "✓ PyYAML installed"

# Check optional dependencies
if python3 -c "import anthropic" 2>/dev/null; then
    echo "✓ anthropic SDK installed (optional, for Layer 2)"
else
    echo "ℹ anthropic SDK not installed (optional, for Layer 2 LLM classification)"
    echo "   Install with: pip install anthropic"
fi

echo ""
echo "✓ All required dependencies satisfied"
exit 0
