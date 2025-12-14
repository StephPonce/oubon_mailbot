#!/bin/bash

#===============================================================================
# G4 FEEDBACK LOOP - CELERY STARTUP SCRIPT
#===============================================================================
#
# This script starts both Celery Worker and Celery Beat for the G4 feedback loop
#
# Usage:
#   chmod +x scripts/start_g4_celery.sh
#   ./scripts/start_g4_celery.sh
#
# Or run components separately:
#   ./scripts/start_g4_celery.sh worker    # Start worker only
#   ./scripts/start_g4_celery.sh beat      # Start beat only
#
#===============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Navigate to project root
cd "$(dirname "$0")/.."

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🚀 G4: COMPLETE FEEDBACK LOOP - CELERY STARTUP${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if Redis is running
echo -e "${YELLOW}📡 Checking Redis connection...${NC}"
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis is running${NC}"
else
    echo -e "${RED}❌ Redis is not running!${NC}"
    echo -e "${YELLOW}Please start Redis first:${NC}"
    echo -e "   ${BLUE}brew services start redis${NC}  (or)  ${BLUE}redis-server${NC}"
    exit 1
fi

echo ""

# Function to start Celery Worker
start_worker() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🔧 Starting Celery Worker...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}Worker will process tasks from all queues:${NC}"
    echo -e "  • ${GREEN}default${NC} - Standard tasks"
    echo -e "  • ${GREEN}high_priority${NC} - Auto-pilot actions"
    echo -e "  • ${GREEN}low_priority${NC} - Analytics & learning"
    echo -e "  • ${GREEN}scheduled${NC} - Scheduled tasks from Beat"
    echo ""

    uv run celery -A ospra_os.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        --max-tasks-per-child=100
}

# Function to start Celery Beat
start_beat() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}⏰ Starting Celery Beat Scheduler...${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}G4 Feedback Loop Schedule:${NC}"
    echo -e "  • ${GREEN}Every 6 hours${NC} - Sync sales data from Shopify"
    echo -e "  • ${GREEN}Daily at 2 AM${NC} - Evaluate AI predictions vs reality"
    echo -e "  • ${GREEN}Daily at 3 AM${NC} - Process learning & update AI weights"
    echo -e "  • ${GREEN}Daily at 4 AM${NC} - Complete feedback loop (master task)"
    echo -e "  • ${GREEN}Weekly Mon 1 AM${NC} - Update global AI weights"
    echo ""

    uv run celery -A ospra_os.celery_app beat \
        --loglevel=info
}

# Main execution
case "${1:-all}" in
    worker)
        start_worker
        ;;
    beat)
        start_beat
        ;;
    all|*)
        echo -e "${YELLOW}Starting both Worker and Beat in parallel...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop both services${NC}"
        echo ""

        # Start worker in background
        start_worker &
        WORKER_PID=$!

        # Wait a moment for worker to initialize
        sleep 3

        # Start beat in foreground
        start_beat &
        BEAT_PID=$!

        # Trap Ctrl+C to kill both processes
        trap "echo -e '\n${YELLOW}Stopping Celery services...${NC}'; kill $WORKER_PID $BEAT_PID 2>/dev/null; exit" INT TERM

        # Wait for both processes
        wait
        ;;
esac
