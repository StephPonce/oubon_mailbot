#!/usr/bin/env bash
set -euo pipefail

PORT=8011
echo ">> Killing anything on port $PORT..."
for p in $(lsof -ti tcp:$PORT); do
  kill -9 "$p" || true
done
pkill -f "uvicorn.*main:app" 2>/dev/null || true
sleep 0.5

echo ">> Starting Oubon MailBot on port $PORT"
exec uvicorn main:app --reload --host 127.0.0.1 --port $PORT
