#!/bin/bash

# Script to create a clean zip package for Grok AI
# Excludes large/unnecessary folders

echo "🚀 Creating Grok AI package..."
echo ""

# Navigate to project root
cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"

# Create output directory
OUTPUT_DIR="$HOME/Desktop"
OUTPUT_FILE="$OUTPUT_DIR/ospra-os-for-grok.zip"

echo "📦 Packaging project (excluding node_modules, .git, etc.)..."
echo "   Output: $OUTPUT_FILE"
echo ""

# Create zip excluding large folders
zip -r "$OUTPUT_FILE" . \
  -x "frontend/node_modules/*" \
  -x "frontend/dist/*" \
  -x "frontend/build/*" \
  -x ".git/*" \
  -x ".venv/*" \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x ".DS_Store" \
  -x ".idea/*" \
  -x ".vscode/*" \
  -x "*.log" \
  -x "data/reports/*" \
  -x ".secrets/*" \
  -x "*.db" \
  -x "*.sqlite" \
  -x "uv.lock" \
  -x ".env" \
  -q  # Quiet mode

# Get file size
if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ Package created successfully!"
    echo "   Size: $FILE_SIZE"
    echo "   Location: $OUTPUT_FILE"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Find 'ospra-os-for-grok.zip' on your Desktop"
    echo "   2. Upload it to Grok in your chat"
    echo "   3. Also attach PROJECT_OVERVIEW_FOR_GROK.md"
    echo ""
    echo "🎯 Quick summary to send Grok:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Tech Stack:"
    echo "  Frontend: React 18 + TypeScript + Vite + Tailwind"
    echo "  Backend: FastAPI (Python) + SQLite"
    echo "  UI: Custom glassmorphic design (no shadcn/MUI)"
    echo ""
    echo "Database: SQLite (async SQLAlchemy)"
    echo "  Tables: stores, products, orders, discovered_products"
    echo ""
    echo "Custom Logic:"
    echo "  - Product discovery with velocity scoring (0-1)"
    echo "  - AI-powered niche classification"
    echo "  - Inventory forecasting algorithm"
    echo "  - Customer segmentation (VIP/Loyal/Regular/One-time)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "❌ Failed to create package"
    exit 1
fi
