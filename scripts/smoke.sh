#!/usr/bin/env bash
set -euo pipefail
base="${1:-http://127.0.0.1:8011}"
echo "HEALTH"; curl -sS "$base/health" ; echo
echo "FORECAST"; curl -sS "$base/forecast/test?h=7" | head -c 400 ; echo ; echo
echo "AI PREVIEW"; curl -sS -X POST "$base/ai/preview" -H 'Content-Type: application/json' --data-binary '{"subject":"Order OU12345","body":"Where is my package?"}' ; echo
echo "RESEARCH QUEUE"; curl -sS "$base/admin/research/queue" ; echo
