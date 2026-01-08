#!/bin/bash
# =============================================================================
# OSPRA INTELLIGENCE - CLEANUP SCRIPT
# =============================================================================
# Removes obsolete discovery engine versions and duplicate files
# Run this from the project root directory
#
# Usage: bash scripts/cleanup_obsolete_files.sh
# =============================================================================

echo "🧹 OSPRA INTELLIGENCE CLEANUP"
echo "=============================="
echo ""

cd "$(dirname "$0")/.." || exit 1

INTELLIGENCE_DIR="ospra_os/intelligence"

# Files to delete (superseded by product_discovery.py)
# NOTE: Cross-reference logic is built INTO product_discovery.py
OBSOLETE_FILES=(
    # Old versioned engines (now consolidated into product_discovery.py)
    "product_intelligence_v4.py"
    "product_intelligence_v5.py"
    
    # Duplicate/unused discovery files
    "ospra_engine.py"
    "ospra_routes.py"
    "enhanced_discovery.py"
    "trend_first_discovery.py"
    "true_cross_source_discovery.py"
    
    # Unused standalone files (functionality merged into main engine)
    "autonomous_ai.py"
    "auto_competitor_discovery.py"
    "competitor_engine.py"
    "competitor_scraper.py"
    "comprehensive_market_analysis.py"
    "gap_analyzer.py"
    "ai_research_agent.py"
    "ai_analyst.py"
)

echo "📁 Target directory: $INTELLIGENCE_DIR"
echo ""
echo "Files to remove:"
echo "----------------"

deleted=0
skipped=0

for file in "${OBSOLETE_FILES[@]}"; do
    filepath="$INTELLIGENCE_DIR/$file"
    if [ -f "$filepath" ]; then
        echo "  ❌ $file"
        rm -f "$filepath"
        ((deleted++))
    else
        echo "  ⏭️  $file (not found)"
        ((skipped++))
    fi
done

echo ""
echo "=============================="
echo "✅ Deleted: $deleted files"
echo "⏭️  Skipped: $skipped files (already removed or don't exist)"
echo ""

# Clean up __pycache__
echo "🗑️  Cleaning __pycache__..."
find ospra_os -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
echo "✅ Cache cleared"
echo ""

echo "🎉 Cleanup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CANONICAL ENGINE: ospra_os/intelligence/product_discovery.py"
echo ""
echo "All cross-referencing logic is BUILT INTO the main engine:"
echo "  - Multi-source fetching (AliExpress, CJ, TikTok, Amazon)"
echo "  - Trend validation (Google Trends)"  
echo "  - Sentiment enrichment (X/Twitter, Reddit)"
echo "  - Score calculation combining ALL sources"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
