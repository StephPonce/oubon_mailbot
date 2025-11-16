#!/bin/bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 COMPREHENSIVE DASHBOARD DIAGNOSTIC"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "1️⃣ CHECKING DEPENDENCIES..."
echo "React version:"
npm list react | grep react@ | head -1
echo "React-dom version:"
npm list react-dom | grep react-dom@ | head -1
echo "Lucide-react version:"
npm list lucide-react | grep lucide-react@ | head -1
echo ""

echo "2️⃣ CHECKING COMPONENT FILES..."
echo "Total components:"
find src/components -name "*.tsx" -type f | wc -l | xargs echo ""
echo "Missing components:"
for comp in ErrorBoundary.tsx ClaudePanel.tsx StatsCard.tsx EmailMetricsPanel.tsx Header.tsx Sidebar.tsx NicheSelector.tsx Pagination.tsx ProductCard.tsx ProductDetailModal.tsx ProfitFilter.tsx SortFilter.tsx; do
    if [ ! -f "src/components/**/$comp" ] && [ ! -f "src/components/*/$comp" ]; then
        echo "  ❌ $comp"
    fi
done
echo ""

echo "3️⃣ CHECKING CRITICAL FILES..."
test -f "src/App.tsx" && echo "✅ App.tsx" || echo "❌ App.tsx"
test -f "src/main.tsx" && echo "✅ main.tsx" || echo "❌ main.tsx"
test -f "src/index.css" && echo "✅ index.css" || echo "❌ index.css"
test -f "src/lib/api.ts" && echo "✅ api.ts" || echo "❌ api.ts"
test -f "src/types/index.ts" && echo "✅ types/index.ts" || echo "❌ types/index.ts"
test -f "index.html" && echo "✅ index.html" || echo "❌ index.html"
echo ""

echo "4️⃣ CHECKING SERVERS..."
echo "Frontend (port 5173):"
curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:5173/ 2>/dev/null || echo "  ❌ Not responding"
echo "Backend (port 8001):"
curl -s -o /dev/null -w "  Status: %{http_code}\n" http://127.0.0.1:8001/health 2>/dev/null || echo "  ❌ Not responding"
echo ""

echo "5️⃣ CHECKING TYPESCRIPT..."
npx tsc --noEmit 2>&1 | head -5 | grep -q "error" && echo "❌ TypeScript errors found" || echo "✅ No TypeScript errors"
echo ""

echo "6️⃣ CHECKING NODE_MODULES..."
test -d "node_modules" && echo "✅ node_modules exists" || echo "❌ node_modules missing"
test -d "node_modules/react" && echo "✅ react installed" || echo "❌ react not installed"
test -d "node_modules/lucide-react" && echo "✅ lucide-react installed" || echo "❌ lucide-react not installed"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DIAGNOSIS COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
