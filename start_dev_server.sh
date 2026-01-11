#!/bin/bash
# Development server starter - loads .env and starts OspraOS

# Load .env file (excluding DATABASE_URL - use SQLite for local dev)
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^DATABASE_URL' | xargs)
    echo "✅ Loaded environment variables from .env (using SQLite for local development)"
fi

echo "🚀 Starting OspraOS development server on port 8001..."
echo "💾 Using SQLite (local dev) - PostgreSQL is used in production on Render"
echo ""

uv run uvicorn ospra_os.main:app --reload --port 8001
