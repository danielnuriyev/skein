#!/bin/bash

# Stop script for Goose Task Server and LiteLLM proxy
# This script stops both services by killing processes on their ports

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Stopping Goose Task Server services..."

# Get PIDs of processes running on the ports
PIDS=$(lsof -ti:4321,8765 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    echo "ℹ️  No services running on ports 4321 or 8765."
    echo "✅ Services are already stopped."
else
    RUNNING=$(echo "$PIDS" | wc -l | tr -d ' ')
    echo "Stopping $RUNNING service(s) on ports 4321 (LiteLLM) and 8765 (Goose server)..."
    echo "$PIDS" | xargs kill -9

    # Wait a moment for processes to terminate
    sleep 1

    # Check if any processes are still running
    if lsof -ti:4321,8765 >/dev/null 2>&1; then
        REMAINING=1
    else
        REMAINING=0
    fi

    if [ "$REMAINING" -eq 0 ]; then
        echo "✅ All services stopped successfully!"
    else
        echo "⚠️  Some processes may still be running. Try again or check manually:"
        echo "   lsof -ti:4321,8765"
    fi
fi

echo ""
echo "To restart services:"
echo "  ./scripts/start_server.sh"