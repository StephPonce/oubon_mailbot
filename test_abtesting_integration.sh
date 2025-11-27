#!/bin/bash

# Full Integration Test for A/B Testing Framework
# Tests: Backend API + Database + Frontend (via curl)

API_BASE="http://localhost:8001"
FRONTEND="http://localhost:5173"

echo "========================================="
echo "A/B TESTING FULL INTEGRATION TEST"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function
test_endpoint() {
  local name="$1"
  local url="$2"
  local expected="$3"

  echo -n "Testing: $name... "
  response=$(curl -s "$url")

  if echo "$response" | grep -q "$expected"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}"
    echo "  Expected: $expected"
    echo "  Got: $response"
    ((TESTS_FAILED++))
  fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  BACKEND HEALTH CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_endpoint "Backend health" "$API_BASE/health" "ok"
test_endpoint "A/B Testing API" "$API_BASE/api/abtesting/tests" "success"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  FRONTEND ACCESSIBILITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_endpoint "Frontend main page" "$FRONTEND" "<!DOCTYPE html>"
test_endpoint "Frontend A/B Testing route" "$FRONTEND/abtesting" "<!DOCTYPE html>"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  CREATE TESTS (All Types)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create Price Test
echo -n "Creating price test... "
PRICE_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/price" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "int-test-prod-001",
    "store_id": "1",
    "current_price": 49.99,
    "test_prices": [39.99, 59.99, 44.99],
    "duration_days": 7,
    "min_sample_size": 50
  }')

PRICE_TEST_ID=$(echo "$PRICE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('test_id', 0))" 2>/dev/null)

if [ "$PRICE_TEST_ID" != "0" ] && [ -n "$PRICE_TEST_ID" ]; then
  echo -e "${GREEN}✓ PASS${NC} (ID: $PRICE_TEST_ID)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((TESTS_FAILED++))
fi

# Create Title Test
echo -n "Creating title test... "
TITLE_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/title" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "int-test-prod-002",
    "store_id": "1",
    "current_title": "Premium Wireless Earbuds",
    "variant_titles": [
      "Wireless Earbuds - Crystal Clear Sound",
      "Premium Audio: Wireless Earbuds with Noise Canceling"
    ],
    "duration_days": 14
  }')

TITLE_TEST_ID=$(echo "$TITLE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('test_id', 0))" 2>/dev/null)

if [ "$TITLE_TEST_ID" != "0" ] && [ -n "$TITLE_TEST_ID" ]; then
  echo -e "${GREEN}✓ PASS${NC} (ID: $TITLE_TEST_ID)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((TESTS_FAILED++))
fi

# Create Description Test
echo -n "Creating description test... "
DESC_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/description" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "int-test-prod-003",
    "store_id": "1",
    "current_description": "High-quality wireless earbuds with premium sound.",
    "variant_descriptions": [
      "Experience premium audio with our wireless earbuds. Features: Noise canceling, 24hr battery, waterproof design.",
      "Wireless earbuds designed for audiophiles. Premium drivers deliver crystal-clear sound. Order now!"
    ],
    "duration_days": 14
  }')

DESC_TEST_ID=$(echo "$DESC_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('test_id', 0))" 2>/dev/null)

if [ "$DESC_TEST_ID" != "0" ] && [ -n "$DESC_TEST_ID" ]; then
  echo -e "${GREEN}✓ PASS${NC} (ID: $DESC_TEST_ID)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((TESTS_FAILED++))
fi

# Create Image Test
echo -n "Creating image test... "
IMAGE_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/image" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "int-test-prod-004",
    "store_id": "1",
    "current_image_url": "https://example.com/earbuds-white-bg.jpg",
    "variant_image_urls": [
      "https://example.com/earbuds-lifestyle.jpg",
      "https://example.com/earbuds-closeup.jpg"
    ],
    "duration_days": 14
  }')

IMAGE_TEST_ID=$(echo "$IMAGE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('test_id', 0))" 2>/dev/null)

if [ "$IMAGE_TEST_ID" != "0" ] && [ -n "$IMAGE_TEST_ID" ]; then
  echo -e "${GREEN}✓ PASS${NC} (ID: $IMAGE_TEST_ID)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((TESTS_FAILED++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  TEST LIFECYCLE OPERATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$PRICE_TEST_ID" != "0" ]; then
  # Start test
  echo -n "Starting price test... "
  START_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/$PRICE_TEST_ID/start")
  if echo "$START_RESPONSE" | grep -q "running"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
  fi

  # Pause test
  echo -n "Pausing price test... "
  PAUSE_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/$PRICE_TEST_ID/pause")
  if echo "$PAUSE_RESPONSE" | grep -q "paused"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
  fi

  # Resume test
  echo -n "Resuming price test... "
  RESUME_RESPONSE=$(curl -s -X POST "$API_BASE/api/abtesting/tests/$PRICE_TEST_ID/resume")
  if echo "$RESUME_RESPONSE" | grep -q "running"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  TEST DATA RETRIEVAL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get all tests
echo -n "Retrieving all tests... "
ALL_TESTS=$(curl -s "$API_BASE/api/abtesting/tests")
TEST_COUNT=$(echo "$ALL_TESTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 0))" 2>/dev/null)

if [ "$TEST_COUNT" -ge "4" ]; then
  echo -e "${GREEN}✓ PASS${NC} ($TEST_COUNT tests found)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC} (Expected >= 4, got $TEST_COUNT)"
  ((TESTS_FAILED++))
fi

# Get test details
if [ "$PRICE_TEST_ID" != "0" ]; then
  echo -n "Retrieving test details... "
  TEST_DETAILS=$(curl -s "$API_BASE/api/abtesting/tests/$PRICE_TEST_ID?include_results=true")
  if echo "$TEST_DETAILS" | grep -q "variants"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
  fi
fi

# Get statistical significance
if [ "$PRICE_TEST_ID" != "0" ]; then
  echo -n "Checking statistical significance... "
  SIGNIFICANCE=$(curl -s "$API_BASE/api/abtesting/tests/$PRICE_TEST_ID/significance")
  if echo "$SIGNIFICANCE" | grep -q "p_value"; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  FILTER TESTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Filter by status
echo -n "Filter by status (running)... "
RUNNING_TESTS=$(curl -s "$API_BASE/api/abtesting/tests?status=running")
if echo "$RUNNING_TESTS" | grep -q "success"; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((TESTS_FAILED++))
fi

# Filter by type
echo -n "Filter by type (price)... "
PRICE_TESTS=$(curl -s "$API_BASE/api/abtesting/tests?test_type=price")
if echo "$PRICE_TESTS" | grep -q "success"; then
  echo -e "${GREEN}✓ PASS${NC}"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}"
  ((TESTS_FAILED++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7️⃣  SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
SUCCESS_RATE=$(python3 -c "print(f'{$TESTS_PASSED/$TOTAL_TESTS*100:.1f}')" 2>/dev/null)

echo "Total Tests: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
echo "Success Rate: ${SUCCESS_RATE}%"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo -e "${GREEN}========================================="
  echo "✅ ALL TESTS PASSED!"
  echo -e "=========================================${NC}"
  exit 0
else
  echo -e "${YELLOW}========================================="
  echo "⚠️  SOME TESTS FAILED"
  echo -e "=========================================${NC}"
  exit 1
fi
