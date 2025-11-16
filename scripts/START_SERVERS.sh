#!/bin/bash

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 STARTING ALL OUBON SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if already running
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "⚠️  Port 8000 already in use (Legacy MailBot already running)"
else
  echo "🔵 Starting Backend 1: Legacy MailBot (Port 8000)..."
  uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
  sleep 2
  echo "   ✅ Started at http://0.0.0.0:8000"
fi

if lsof -ti:8001 >/dev/null 2>&1; then
  echo "⚠️  Port 8001 already in use (OspraOS already running)"
else
  echo "🟣 Starting Backend 2: OspraOS Platform (Port 8001)..."
  uv run uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload &
  sleep 2
  echo "   ✅ Started at http://0.0.0.0:8001"
fi

if lsof -ti:5173 >/dev/null 2>&1; then
  echo "⚠️  Port 5173 already in use (Frontend already running)"
else
  echo "🎨 Starting Frontend Dashboard (Port 5173)..."
  cd frontend && npm run dev &
  sleep 3
  echo "   ✅ Started at http://localhost:5173"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ ALL SERVICES RUNNING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access URLs:"
echo "   • Frontend:     http://localhost:5173"
echo "   • Legacy API:   http://0.0.0.0:8000/docs"
echo "   • OspraOS API:  http://0.0.0.0:8001/docs"
echo ""
echo "To stop all services, run: ./STOP_SERVERS.sh"
echo ""
