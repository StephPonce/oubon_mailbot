#!/usr/bin/env bash
# CI/CD Test Runner for OspraOS
# Optimized for continuous integration environments
# Usage: ./scripts/run_tests_ci.sh [unit|integration|e2e|all]

set -e

# Parse arguments
TEST_TYPE="${1:-all}"

# Validate test type
case "$TEST_TYPE" in
    unit|integration|e2e|all)
        ;;
    *)
        echo "ERROR: Invalid test type '$TEST_TYPE'"
        echo "Usage: ./scripts/run_tests_ci.sh [unit|integration|e2e|all]"
        exit 1
        ;;
esac

# Ensure we're in the project root
cd "$(dirname "$0")/.."

echo "========================================="
echo "OspraOS CI Test Suite"
echo "========================================="
echo "Test Type: $TEST_TYPE"
echo "Python: $(python3 --version)"
echo "Pytest: $(uv run pytest --version)"
echo "========================================="
echo ""

# Build pytest command
PYTEST_ARGS="-v --strict-markers --strict-config"

# Add marker filter based on test type
if [ "$TEST_TYPE" != "all" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -m $TEST_TYPE"
fi

# CI-specific options
PYTEST_ARGS="$PYTEST_ARGS --tb=short"           # Shorter tracebacks
PYTEST_ARGS="$PYTEST_ARGS --maxfail=5"          # Stop after 5 failures
PYTEST_ARGS="$PYTEST_ARGS --no-header"          # No header for cleaner logs
PYTEST_ARGS="$PYTEST_ARGS --durations=20"       # Show 20 slowest tests
PYTEST_ARGS="$PYTEST_ARGS --cov-report=xml"     # XML for CI coverage tools
PYTEST_ARGS="$PYTEST_ARGS --cov-report=term"    # Terminal summary

# Run tests
echo "Running tests..."
uv run pytest $PYTEST_ARGS

EXIT_CODE=$?

echo ""
echo "========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ CI Tests PASSED"
else
    echo "❌ CI Tests FAILED (exit code: $EXIT_CODE)"
fi
echo "========================================="

# Print coverage summary location
if [ -f coverage.xml ]; then
    echo "Coverage report: coverage.xml"
fi

exit $EXIT_CODE
