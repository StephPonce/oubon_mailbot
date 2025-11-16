#!/bin/bash

# Kill everything
pkill -f "vite" || true
pkill -f "uvicorn ospra_os" || true
sleep 2

# Start backend
cd "/Users/stephenponce/Documents/Ospra OS/Bots/oubon_mailbot"
source .venv/bin/activate
python -m uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload > logs/backend.log 2>&1 &

sleep 3

# Start frontend
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &

sleep 5

echo "✅ Servers started"
echo ""
echo "Backend: http://localhost:8001"
echo "Frontend: http://localhost:5173"
echo ""
echo "Check logs:"
echo "  tail -f logs/backend.log"
echo "  tail -f logs/frontend.log"
