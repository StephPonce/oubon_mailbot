#!/bin/bash
# =============================================================================
# OSPRA INTELLIGENCE - DEPENDENCY FIX SCRIPT
# =============================================================================
# Run this to fix pytrends and other dependency issues
# Usage: ./scripts/fix_dependencies.sh
# =============================================================================

set -e

echo "🔧 OSPRA DEPENDENCY FIX"
echo "======================"

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "📦 Found .venv - activating..."
    source .venv/bin/activate
else
    echo "❌ No .venv found - creating..."
    python3 -m venv .venv
    source .venv/bin/activate
fi

echo ""
echo "📥 Upgrading pytrends (fixes urllib3 compatibility)..."
pip install --upgrade pytrends

echo ""
echo "📥 Upgrading urllib3 (ensures compatibility)..."
pip install --upgrade urllib3

echo ""
echo "📥 Installing/upgrading key packages..."
pip install --upgrade requests aiohttp httpx

echo ""
echo "✅ Dependencies fixed!"
echo ""
echo "🧪 Test by running:"
echo "   python tests/test_full_discovery_pipeline.py"
