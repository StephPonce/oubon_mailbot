#!/bin/bash

# A/B Testing API Test Script
# Tests all major endpoints

API_BASE="http://localhost:8001"

echo "========================================="
echo "A/B TESTING API TEST SUITE"
echo "========================================="
echo ""

# Test 1: Get all tests (should be empty initially)
echo "1️⃣ GET /api/abtesting/tests"
curl -s -X GET "$API_BASE/api/abtesting/tests" | python3 -m json.tool
echo ""
echo ""

# Test 2: Create a price test
echo "2️⃣ POST /api/abtesting/tests/price"
PRICE_TEST=$(curl -s -X POST "$API_BASE/api/abtesting/tests/price" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test-product-123",
    "store_id": "1",
    "current_price": 29.99,
    "test_prices": [24.99, 34.99],
    "test_name": "Price Test: Smart Watch",
    "duration_days": 7,
    "min_sample_size": 50
  }')
echo "$PRICE_TEST" | python3 -m json.tool
TEST_ID=$(echo "$PRICE_TEST" | python3 -c "import sys, json; print(json.load(sys.stdin).get('test_id', 0))")
echo ""
echo "Created test ID: $TEST_ID"
echo ""

# Test 3: Get test details
if [ "$TEST_ID" != "0" ]; then
  echo "3️⃣ GET /api/abtesting/tests/$TEST_ID"
  curl -s -X GET "$API_BASE/api/abtesting/tests/$TEST_ID?include_results=true" | python3 -m json.tool
  echo ""
  echo ""

  # Test 4: Start the test
  echo "4️⃣ POST /api/abtesting/tests/$TEST_ID/start"
  curl -s -X POST "$API_BASE/api/abtesting/tests/$TEST_ID/start" | python3 -m json.tool
  echo ""
  echo ""

  # Test 5: Record some test data (impression + conversion)
  echo "5️⃣ POST /api/abtesting/events/impression"
  curl -s -X POST "$API_BASE/api/abtesting/events/impression" \
    -H "Content-Type: application/json" \
    -d "{
      \"test_id\": $TEST_ID,
      \"visitor_id\": \"visitor-001\"
    }" | python3 -m json.tool
  echo ""
  echo ""

  echo "6️⃣ POST /api/abtesting/events/conversion"
  curl -s -X POST "$API_BASE/api/abtesting/events/conversion" \
    -H "Content-Type: application/json" \
    -d "{
      \"test_id\": $TEST_ID,
      \"visitor_id\": \"visitor-001\",
      \"revenue\": 24.99
    }" | python3 -m json.tool
  echo ""
  echo ""

  # Test 6: Get updated test results
  echo "7️⃣ GET /api/abtesting/tests/$TEST_ID (with results)"
  curl -s -X GET "$API_BASE/api/abtesting/tests/$TEST_ID?include_results=true" | python3 -m json.tool
  echo ""
  echo ""

  # Test 7: Get statistical significance
  echo "8️⃣ GET /api/abtesting/tests/$TEST_ID/significance"
  curl -s -X GET "$API_BASE/api/abtesting/tests/$TEST_ID/significance" | python3 -m json.tool
  echo ""
  echo ""

  # Test 8: Pause the test
  echo "9️⃣ POST /api/abtesting/tests/$TEST_ID/pause"
  curl -s -X POST "$API_BASE/api/abtesting/tests/$TEST_ID/pause" | python3 -m json.tool
  echo ""
  echo ""

  # Test 9: Resume the test
  echo "🔟 POST /api/abtesting/tests/$TEST_ID/resume"
  curl -s -X POST "$API_BASE/api/abtesting/tests/$TEST_ID/resume" | python3 -m json.tool
  echo ""
  echo ""
fi

# Test 10: Create a title test
echo "1️⃣1️⃣ POST /api/abtesting/tests/title"
curl -s -X POST "$API_BASE/api/abtesting/tests/title" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "test-product-456",
    "store_id": "1",
    "current_title": "Smart Watch with Fitness Tracker",
    "variant_titles": [
      "Premium Fitness Smart Watch - Track Your Health",
      "Smart Watch: Monitor Heart Rate, Sleep & Steps"
    ],
    "duration_days": 14
  }' | python3 -m json.tool
echo ""
echo ""

# Test 11: Get all tests again (should have 2 now)
echo "1️⃣2️⃣ GET /api/abtesting/tests (final check)"
curl -s -X GET "$API_BASE/api/abtesting/tests" | python3 -m json.tool
echo ""
echo ""

# Test 12: Get price recommendations
echo "1️⃣3️⃣ GET /api/abtesting/recommendations/price"
curl -s -X GET "$API_BASE/api/abtesting/recommendations/price?product_id=test-product-123&store_id=1&current_price=29.99" | python3 -m json.tool
echo ""
echo ""

echo "========================================="
echo "✅ A/B TESTING API TEST COMPLETE"
echo "========================================="
