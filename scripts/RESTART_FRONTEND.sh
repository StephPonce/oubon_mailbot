#!/bin/bash
set -e

echo "🔄 Restarting frontend..."

# Kill frontend
pkill -f "vite" || true
sleep 2

# Start frontend
cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS/frontend"
npm run dev &

sleep 5

echo "✅ Frontend running on http://localhost:5173"
