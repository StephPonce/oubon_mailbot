#!/bin/bash

echo "🛑 Stopping all Oubon services..."
echo ""

# Stop port 8000 (Legacy MailBot)
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "🔵 Stopping Legacy MailBot (port 8000)..."
  lsof -ti:8000 | xargs kill -9
  echo "   ✅ Stopped"
else
  echo "   ℹ️  Port 8000 not in use"
fi

# Stop port 8001 (OspraOS)
if lsof -ti:8001 >/dev/null 2>&1; then
  echo "🟣 Stopping OspraOS Platform (port 8001)..."
  lsof -ti:8001 | xargs kill -9
  echo "   ✅ Stopped"
else
  echo "   ℹ️  Port 8001 not in use"
fi

# Stop port 5173 (Frontend)
if lsof -ti:5173 >/dev/null 2>&1; then
  echo "🎨 Stopping Frontend (port 5173)..."
  lsof -ti:5173 | xargs kill -9
  echo "   ✅ Stopped"
else
  echo "   ℹ️  Port 5173 not in use"
fi

echo ""
echo "✅ All services stopped"
