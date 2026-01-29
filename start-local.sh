#!/bin/bash
# =============================================================================
# OSPRA OS - Local Development Starter
# =============================================================================
# Usage: ./start-local.sh
#
# This starts both backend and frontend for local development.
# Press Ctrl+C to stop both.

echo "🚀 Starting Ospra OS Local Development..."
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found!"
    echo "   Copy .env.local to .env and add your Neon DATABASE_URL"
    echo "   Run: cp .env.local .env"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start backend
echo "📦 Starting Backend (localhost:8000)..."
cd "$(dirname "$0")"
python -m uvicorn ospra_os.main:app --reload --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start frontend
echo "🎨 Starting Frontend (localhost:5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Ospra OS is running!"
echo ""
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Wait for both processes
wait
