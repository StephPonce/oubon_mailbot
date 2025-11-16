#!/bin/bash
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 FIXING BLANK PAGE ISSUE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Step 1: Killing all existing servers..."
pkill -f vite 2>/dev/null
pkill -f "npm run dev" 2>/dev/null
sleep 2
echo "✅ Servers stopped"
echo ""

echo "Step 2: Clearing caches..."
rm -rf node_modules/.vite 2>/dev/null
echo "✅ Vite cache cleared"
echo ""

echo "Step 3: Verifying React 18..."
REACT_VERSION=$(npm list react | grep react@ | head -1 | grep -o '@[0-9.]*' | cut -d@ -f2)
if [[ "$REACT_VERSION" == 18.* ]]; then
    echo "✅ React 18 installed: $REACT_VERSION"
else
    echo "⚠️  React version: $REACT_VERSION (reinstalling 18.3.1...)"
    npm install --save-exact react@18.3.1 react-dom@18.3.1 --legacy-peer-deps 2>/dev/null
fi
echo ""

echo "Step 4: Starting Vite server..."
npm run dev -- --host 0.0.0.0 > /tmp/vite.log 2>&1 &
VITE_PID=$!
echo "Vite PID: $VITE_PID"
sleep 4
echo ""

echo "Step 5: Checking server status..."
if curl -s http://localhost:5173/ > /dev/null 2>&1; then
    echo "✅ Vite server is running!"
    echo "   URL: http://localhost:5173"
else
    echo "❌ Vite server failed to start"
    echo "Check logs: tail -50 /tmp/vite.log"
    exit 1
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ FIX COMPLETE!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 NEXT STEPS:"
echo "1. Open browser: http://localhost:5173"
echo "2. Hard refresh: Cmd + Shift + R"
echo "3. If still blank, open DevTools (right-click → Inspect → Console)"
echo "4. Screenshot any red errors and share with Claude"
echo ""
