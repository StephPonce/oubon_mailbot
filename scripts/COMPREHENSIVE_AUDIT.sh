#!/bin/bash

# COMPREHENSIVE PROJECT AUDIT SCRIPT
# Analyzes entire OspraOS project for issues, unused files, and system health

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 OSPRA OS - COMPREHENSIVE PROJECT AUDIT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Started: $(date)"
echo ""

# Change to project directory
cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"

# ============================================================================
# SECTION 1: PROJECT STRUCTURE ANALYSIS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 SECTION 1: PROJECT STRUCTURE ANALYSIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📊 Total Python Files:"
find . -name "*.py" -not -path "./.venv/*" -not -path "./node_modules/*" | wc -l

echo ""
echo "📊 Total TypeScript/React Files:"
find ./frontend/src -name "*.tsx" -o -name "*.ts" | wc -l

echo ""
echo "📊 Total Markdown Documentation:"
find . -name "*.md" -not -path "./node_modules/*" -not -path "./.venv/*" | wc -l

echo ""
echo "📊 Lines of Code:"
echo "  Python:"
find . -name "*.py" -not -path "./.venv/*" -not -path "./node_modules/*" -exec wc -l {} + | tail -1
echo "  TypeScript/React:"
find ./frontend/src -name "*.tsx" -o -name "*.ts" -exec wc -l {} + | tail -1

echo ""

# ============================================================================
# SECTION 2: PYTHON IMPORT VALIDATION
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐍 SECTION 2: PYTHON IMPORT VALIDATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Testing critical module imports..."
echo ""

# Test importing main app
echo "1. Testing main.py import..."
uv run python -c "from main import app" 2>&1 | grep -q "Error" && echo "   ❌ FAILED" || echo "   ✅ SUCCESS"

# Test importing ospra_os main
echo "2. Testing ospra_os.main import..."
uv run python -c "from ospra_os.main import app" 2>&1 | grep -q "Error" && echo "   ❌ FAILED" || echo "   ✅ SUCCESS"

# Test Intelligence Core modules
echo "3. Testing Intelligence Core modules..."
uv run python -c "from ospra_os.intelligence.unified_context import get_unified_context_builder" 2>&1 | grep -q "Error" && echo "   unified_context: ❌ FAILED" || echo "   unified_context: ✅ SUCCESS"
uv run python -c "from ospra_os.intelligence.briefing_engine import get_briefing_engine" 2>&1 | grep -q "Error" && echo "   briefing_engine: ❌ FAILED" || echo "   briefing_engine: ✅ SUCCESS"
uv run python -c "from ospra_os.intelligence.grade_reasoning import get_grade_reasoning_engine" 2>&1 | grep -q "Error" && echo "   grade_reasoning: ❌ FAILED" || echo "   grade_reasoning: ✅ SUCCESS"
uv run python -c "from ospra_os.intelligence.progress_flow import get_progress_tracker" 2>&1 | grep -q "Error" && echo "   progress_flow: ❌ FAILED" || echo "   progress_flow: ✅ SUCCESS"
uv run python -c "from ospra_os.intelligence.tier_system import get_tier_system" 2>&1 | grep -q "Error" && echo "   tier_system: ❌ FAILED" || echo "   tier_system: ✅ SUCCESS"
uv run python -c "from ospra_os.intelligence.action_executor import get_action_executor" 2>&1 | grep -q "Error" && echo "   action_executor: ❌ FAILED" || echo "   action_executor: ✅ SUCCESS"

echo ""

# ============================================================================
# SECTION 3: API ROUTES INVENTORY
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 SECTION 3: API ROUTES INVENTORY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Testing backend health..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ Backend is running on port 8001"
    echo ""

    echo "Core System Routes:"
    echo "  GET  /health" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health)
    echo "  GET  /api/system/health" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/system/health)

    echo ""
    echo "Intelligence Core Routes:"
    echo "  GET  /api/intelligence/health" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/intelligence/health)
    echo "  GET  /api/intelligence/briefing/morning" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/intelligence/briefing/morning)
    echo "  GET  /api/intelligence/context/summary" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/intelligence/context/summary)
    echo "  GET  /api/intelligence/tier/info?user_id=1" $(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/intelligence/tier/info?user_id=1")

    echo ""
    echo "Dashboard Routes:"
    echo "  GET  /api/dashboard/v2/overview" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/dashboard/v2/overview)
    echo "  GET  /api/dashboard/v2/niches" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/dashboard/v2/niches)
    echo "  GET  /api/portfolio/overview" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/portfolio/overview)

    echo ""
    echo "Product Routes:"
    echo "  GET  /api/products" $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/products)
    echo "  GET  /api/discovery/products?niche=smart_home" $(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8001/api/discovery/products?niche=smart_home")

else
    echo "❌ Backend is NOT running on port 8001"
    echo "   Please start backend: uv run uvicorn ospra_os.main:app --reload --host 127.0.0.1 --port 8001"
fi

echo ""

# ============================================================================
# SECTION 4: MARKDOWN DOCUMENTATION AUDIT
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 SECTION 4: MARKDOWN DOCUMENTATION AUDIT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "All markdown files in project:"
find . -name "*.md" -not -path "./node_modules/*" -not -path "./.venv/*" | sort

echo ""
echo "Potentially unnecessary documentation files (status/completion MDs):"
find . -name "*_STATUS.md" -o -name "*_COMPLETE.md" -o -name "*_ACTIVATED.md" | grep -v node_modules | grep -v .venv

echo ""

# ============================================================================
# SECTION 5: DATABASE MODELS ANALYSIS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗄️  SECTION 5: DATABASE MODELS ANALYSIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Database model files:"
find . -name "*models.py" -not -path "./.venv/*" -not -path "./node_modules/*"

echo ""
echo "Key models defined in multi_store_models.py:"
grep "^class.*Base" ospra_os/database/multi_store_models.py | head -20

echo ""

# ============================================================================
# SECTION 6: CODE QUALITY CHECKS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 SECTION 6: CODE QUALITY CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "TODO comments in Python files:"
grep -r "# TODO" --include="*.py" . --exclude-dir=.venv --exclude-dir=node_modules | wc -l

echo ""
echo "FIXME comments in Python files:"
grep -r "# FIXME" --include="*.py" . --exclude-dir=.venv --exclude-dir=node_modules | wc -l

echo ""
echo "XXX comments in Python files:"
grep -r "# XXX" --include="*.py" . --exclude-dir=.venv --exclude-dir=node_modules | wc -l

echo ""

# ============================================================================
# SECTION 7: UNUSED/ORPHANED FILES
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  SECTION 7: POTENTIALLY UNUSED FILES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Test files that might be orphaned:"
find . -name "test_*.py" -not -path "./.venv/*" -not -path "./node_modules/*" | grep -v __pycache__

echo ""
echo "Script files (review for necessity):"
find ./scripts -name "*.sh" | sort

echo ""

# ============================================================================
# SECTION 8: GIT STATUS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 SECTION 8: GIT STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Current branch:"
git branch --show-current

echo ""
echo "Modified files:"
git status --short | grep "^ M" | wc -l

echo ""
echo "Untracked files:"
git status --short | grep "^??" | wc -l

echo ""
echo "Deleted files (not committed):"
git status --short | grep "^ D" | wc -l

echo ""

# ============================================================================
# SECTION 9: FRONTEND ANALYSIS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚛️  SECTION 9: FRONTEND ANALYSIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "React components:"
find ./frontend/src/components -name "*.tsx" | wc -l

echo ""
echo "React pages:"
find ./frontend/src/pages -name "*.tsx" | wc -l

echo ""
echo "Frontend health check:"
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ Frontend is running on port 5173"
else
    echo "❌ Frontend is NOT running on port 5173"
fi

echo ""

# ============================================================================
# SECTION 10: DEPENDENCIES AUDIT
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 SECTION 10: DEPENDENCIES AUDIT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Python dependencies (from pyproject.toml):"
grep "dependencies" pyproject.toml -A 30 | head -25

echo ""

# ============================================================================
# SECTION 11: SUMMARY & RECOMMENDATIONS
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 SECTION 11: SUMMARY & RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "RECOMMENDED CLEANUPS:"
echo ""
echo "1. Delete status/completion markdown files:"
echo "   find . -name '*_STATUS.md' -o -name '*_COMPLETE.md' | xargs rm"
echo ""
echo "2. Remove orphaned test files:"
echo "   Review files in root directory starting with 'test_'"
echo ""
echo "3. Clean up scripts directory:"
echo "   Review and consolidate bash scripts in ./scripts"
echo ""
echo "4. Git cleanup:"
echo "   git add . && git commit -m 'feat: complete Intelligence Core integration'"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ AUDIT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Completed: $(date)"
echo ""
