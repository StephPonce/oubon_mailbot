#!/bin/bash

# Test all dashboard pages and API endpoints
# Run this to verify all connections are working

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 OSPRA OS DASHBOARD - FULL API TEST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Testing backend at: http://localhost:8001"
echo "Frontend should be at: http://localhost:5173"
echo ""

BASE_URL="http://localhost:8001"

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local method=${3:-GET}

    printf "%-40s " "$name:"

    if [ "$method" = "POST" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST "$url" -H "Content-Type: application/json" -d '{"query":"test","max_results":5}')
    else
        response=$(curl -s -w "\n%{http_code}" "$url")
    fi

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" = "200" ]; then
        # Check if response has data
        if echo "$body" | grep -q "\"detail\":\"Not Found\""; then
            echo "❌ 404 Not Found"
        elif echo "$body" | python3 -c "import sys,json; data=json.load(sys.stdin); print('ok')" 2>/dev/null; then
            echo "✅ OK (JSON response)"
        else
            echo "⚠️  OK but invalid JSON"
        fi
    else
        echo "❌ HTTP $http_code"
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 PORTFOLIO DASHBOARD APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Portfolio Overview" "$BASE_URL/api/portfolio/overview"
test_endpoint "Portfolio Rankings" "$BASE_URL/api/portfolio/rankings"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 PRODUCTS PAGE APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Products (all niches)" "$BASE_URL/api/dashboard/v2/products?niche=all&per_page=10"
test_endpoint "Products (smart_home)" "$BASE_URL/api/dashboard/v2/products?niche=smart_home&per_page=10"
test_endpoint "Product Discovery" "$BASE_URL/api/intelligence/discover" "POST"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 ANALYTICS PAGE APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Analytics Dashboard" "$BASE_URL/api/dashboard/v2/analytics"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛒 ORDERS PAGE APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Orders List" "$BASE_URL/api/dashboard/v2/orders?limit=10"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📧 EMAIL DASHBOARD APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Email Dashboard Summary" "$BASE_URL/api/dashboard/emails"
test_endpoint "Recent Emails" "$BASE_URL/api/emails/recent"
test_endpoint "Email Stats (Weekly)" "$BASE_URL/api/emails/stats/weekly"
test_endpoint "Email Stats (Categories)" "$BASE_URL/api/emails/stats/categories"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 NICHE ANALYSIS APIs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Available Niches" "$BASE_URL/api/dashboard/v2/niches"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏥 SYSTEM HEALTH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
test_endpoint "Backend Health Check" "$BASE_URL/health"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 DATA SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get actual data counts
echo "Portfolio Overview:"
curl -s "$BASE_URL/api/portfolio/overview" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  • Stores: {d.get(\"total_stores\",0)}'); print(f'  • Products: {d.get(\"total_products\",0)}'); print(f'  • Orders: {d.get(\"total_orders\",0)}'); print(f'  • Revenue: \${d.get(\"total_revenue\",0):.2f}')" 2>/dev/null || echo "  ❌ Could not fetch data"

echo ""
echo "Email System:"
curl -s "$BASE_URL/api/dashboard/emails" | python3 -c "import json,sys; d=json.load(sys.stdin); s=d.get('summary',{}); print(f'  • Today: {s.get(\"processed_today\",0)} emails'); print(f'  • This Week: {s.get(\"processed_week\",0)} emails'); print(f'  • Auto-replied: {s.get(\"auto_replied_today\",0)}'); print(f'  • Response Rate: {d.get(\"response_rate\",0):.1f}%')" 2>/dev/null || echo "  ❌ Could not fetch data"

echo ""
echo "Available Niches:"
curl -s "$BASE_URL/api/dashboard/v2/niches" | python3 -c "import json,sys; d=json.load(sys.stdin); niches=d.get('niches',[]); [print(f'  • {n[\"name\"]} {"📈 Trending" if n.get(\"trending\") else ""}') for n in niches]" 2>/dev/null || echo "  ❌ Could not fetch data"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ TEST COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📱 Frontend Access:"
echo "   • Primary: http://localhost:5173"
echo "   • Alternative: http://127.0.0.1:5173"
echo ""
echo "🔧 Backend Access:"
echo "   • API Base: http://localhost:8001"
echo "   • API Docs: http://localhost:8001/docs"
echo ""
