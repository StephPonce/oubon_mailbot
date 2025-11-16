#!/bin/bash

echo "🔧 FIXING REACT TYPES MISMATCH..."
echo ""

cd "$(dirname "$0")"

# Step 1: Fix React types to match runtime version
echo "Step 1: Downgrading @types/react to match React 18.3.1..."
npm install --save-dev @types/react@18.3.17 @types/react-dom@18.3.5

echo ""
echo "Step 2: Verifying installations..."
npm list react react-dom @types/react @types/react-dom

echo ""
echo "Step 3: Cleaning build artifacts..."
rm -rf node_modules/.vite dist

echo ""
echo "✅ FIXED! Now starting dev server..."
echo ""
npm run dev
