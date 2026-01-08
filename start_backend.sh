#!/bin/bash
# Ospra Intelligence Backend - Auto-restart wrapper
# Usage: ./start_backend.sh

cd "/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS"

# Create logs dir
mkdir -p logs

echo "[$(date)] Starting Ospra Intelligence Backend..."

while true; do
    echo "[$(date)] Backend starting on port 8000..."
    
    # Activate venv and run
    source .venv/bin/activate 2>/dev/null || true
    uvicorn main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a logs/backend.log
    
    EXIT_CODE=$?
    echo "[$(date)] Backend exited with code $EXIT_CODE"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] Clean exit - not restarting"
        break
    fi
    
    echo "[$(date)] Crash detected - restarting in 5 seconds..."
    sleep 5
done
