#!/bin/bash
set -e

echo "🔄 Restarting backend..."

# Kill backend
pkill -f "uvicorn ospra_os.main" || true
sleep 2

# Start backend
cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"
source .venv/bin/activate
python -m uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload > logs/backend.log 2>&1 &

sleep 5

# Test
echo "Testing connection..."
curl -s http://localhost:8001/api/dashboard/v2/health | python3 -m json.tool
echo ""
curl -s http://localhost:8001/api/dashboard/v2/niches | python3 -m json.tool
echo ""
curl -s http://localhost:8001/api/dashboard/v2/overview | python3 -m json.tool

echo ""
echo "✅ Backend running on http://localhost:8001"
