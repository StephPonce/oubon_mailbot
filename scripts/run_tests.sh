#!/usr/bin/env bash
# Development Test Runner for OspraOS
# Usage: ./scripts/run_tests.sh [unit|integration|e2e|all] [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}         OspraOS Test Suite - Development Runner${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Parse arguments
TEST_TYPE="${1:-all}"
shift || true
EXTRA_ARGS="$@"

# Validate test type
case "$TEST_TYPE" in
    unit|integration|e2e|all)
        ;;
    *)
        echo -e "${RED}Error: Invalid test type '$TEST_TYPE'${NC}"
        echo "Usage: ./scripts/run_tests.sh [unit|integration|e2e|all] [pytest options]"
        echo ""
        echo "Examples:"
        echo "  ./scripts/run_tests.sh unit              # Run only unit tests"
        echo "  ./scripts/run_tests.sh integration       # Run only integration tests"
        echo "  ./scripts/run_tests.sh e2e               # Run only e2e tests"
        echo "  ./scripts/run_tests.sh all               # Run all tests (default)"
        echo "  ./scripts/run_tests.sh unit -v           # Run unit tests with verbose output"
        echo "  ./scripts/run_tests.sh all -k test_name  # Run tests matching pattern"
        exit 1
        ;;
esac

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not detected${NC}"
    echo -e "${YELLOW}   Using 'uv run' to execute tests...${NC}"
    echo ""
    PYTHON_CMD="uv run"
else
    echo -e "${GREEN}✓ Virtual environment detected: $VIRTUAL_ENV${NC}"
    echo ""
    PYTHON_CMD=""
fi

# Build pytest command
PYTEST_CMD="pytest"
PYTEST_ARGS="-v"

# Add marker filter based on test type
if [ "$TEST_TYPE" != "all" ]; then
    PYTEST_ARGS="$PYTEST_ARGS -m $TEST_TYPE"
    echo -e "${BLUE}📋 Test Type:${NC} $TEST_TYPE"
else
    echo -e "${BLUE}📋 Test Type:${NC} all tests"
fi

# Add extra arguments
if [ -n "$EXTRA_ARGS" ]; then
    PYTEST_ARGS="$PYTEST_ARGS $EXTRA_ARGS"
    echo -e "${BLUE}🔧 Extra Args:${NC} $EXTRA_ARGS"
fi

echo -e "${BLUE}📁 Test Path:${NC} tests/"
echo ""
echo -e "${YELLOW}Starting test execution...${NC}"
echo ""

# Run tests
if [ -n "$PYTHON_CMD" ]; then
    $PYTHON_CMD $PYTEST_CMD $PYTEST_ARGS
    EXIT_CODE=$?
else
    $PYTEST_CMD $PYTEST_ARGS
    EXIT_CODE=$?
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Print summary
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo -e "${BLUE}📊 Coverage Report:${NC}"
    echo "   HTML: htmlcov/index.html"
    echo "   JSON: coverage.json"
    echo "   Terminal: See above"
    echo ""
    echo -e "${YELLOW}💡 Tip: Open htmlcov/index.html in your browser for detailed coverage${NC}"
else
    echo -e "${RED}❌ Some tests failed${NC}"
    echo ""
    echo -e "${YELLOW}🔍 Debugging tips:${NC}"
    echo "   • Check test.log for detailed logs: cat tests/test.log"
    echo "   • Run specific test: ./scripts/run_tests.sh all -k test_name"
    echo "   • Run with more verbosity: ./scripts/run_tests.sh all -vv"
    echo "   • Show print statements: ./scripts/run_tests.sh all -s"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

exit $EXIT_CODE
