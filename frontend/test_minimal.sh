#!/bin/bash

echo "🔧 TESTING MINIMAL REACT..."
echo ""

cd "$(dirname "$0")"

# Backup current setup
echo "Backing up current main.tsx..."
cp src/main.tsx src/main.tsx.backup.$(date +%s)

# Use minimal test
echo "Switching to minimal test..."
cp src/main.test.tsx src/main.tsx

echo ""
echo "✅ DONE! Now:"
echo "1. Go to http://localhost:5173"
echo "2. Hard refresh: Cmd+Shift+R"
echo ""
echo "If you see '✅ REACT IS WORKING!' → Component issue"
echo "If still blank → Build/setup issue"
echo ""
echo "To restore original:"
echo "  cp src/main.tsx.backup.* src/main.tsx"
