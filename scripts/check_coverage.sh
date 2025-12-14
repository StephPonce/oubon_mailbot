#!/usr/bin/env bash
# Coverage Checker for OspraOS
# Validates test coverage meets minimum thresholds
# Usage: ./scripts/check_coverage.sh [threshold]

set -e

THRESHOLD="${1:-70}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "         OspraOS Coverage Report"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Check if coverage data exists
if [ ! -f .coverage ]; then
    echo "❌ No coverage data found"
    echo "   Run tests first: ./scripts/run_tests.sh"
    exit 1
fi

# Generate coverage report
echo "Generating coverage report..."
echo ""

uv run coverage report --skip-covered

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if coverage meets threshold
COVERAGE=$(uv run coverage report --format=total)

echo ""
echo "📊 Total Coverage: ${COVERAGE}%"
echo "🎯 Required Threshold: ${THRESHOLD}%"
echo ""

if (( $(echo "$COVERAGE >= $THRESHOLD" | bc -l) )); then
    echo "✅ Coverage meets threshold!"
    echo ""
    echo "📁 Detailed reports available:"
    echo "   • HTML: htmlcov/index.html"
    echo "   • JSON: coverage.json"
    echo "   • XML: coverage.xml (for CI)"
    echo ""
    exit 0
else
    echo "❌ Coverage below threshold!"
    echo ""
    echo "🔍 Files with low coverage:"
    uv run coverage report --skip-covered | grep -v "100%"
    echo ""
    exit 1
fi
