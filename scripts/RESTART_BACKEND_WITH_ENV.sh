#!/bin/bash
set -a
source .env
set +a

pkill -f "uvicorn ospra_os" || true
sleep 2

python -m uvicorn ospra_os.main:app --host 0.0.0.0 --port 8001 --reload &

sleep 3
curl -s http://localhost:8001/api/dashboard/v2/health | python3 -m json.tool

echo ""
echo "✅ Backend restarted with environment variables"
