#!/bin/bash

# Start script for Slack middleware server
# This script starts the Slack-to-Goose bridge server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default values
RESTART_SERVICES=true
SLACK_PORT=3000

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --restart)
            RESTART_SERVICES=true
            shift
            ;;
        --no-restart)
            RESTART_SERVICES=false
            shift
            ;;
        --port)
            SLACK_PORT="$2"
            shift
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Start Slack middleware server for Goose integration."
            echo ""
            echo "Options:"
            echo "  --restart         Restart server if already running (default)"
            echo "  --no-restart      Don't restart server if already running"
            echo "  --port PORT       Port to run Slack server on (default: 3000)"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  SLACK_SIGNING_SECRET    For request verification (recommended)"
            echo "  GOOSE_SERVER_URL        URL of src/services/goose_server.py (default: http://localhost:8765)"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start server (restart if running)"
            echo "  $0 --no-restart              # Start server only if not running"
            echo "  $0 --port 8080               # Start on port 8080"
            echo ""
            echo "For Slack integration:"
            echo "  1. Create a Slack App at https://api.slack.com/apps"
            echo "  2. Add a Slash Command (e.g., /goose)"
            echo "  3. Set Request URL to: https://your-domain.ngrok.io/slack/command"
            echo "  4. Use ngrok to expose port ${SLACK_PORT}: ngrok http ${SLACK_PORT}"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

echo "Starting Slack middleware server..."

# Kill existing process on the specified port if restart is enabled
if [ "$RESTART_SERVICES" = true ]; then
    echo "Checking for existing processes on port ${SLACK_PORT}..."
    lsof -ti:"${SLACK_PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
else
    echo "Checking if Slack server is already running on port ${SLACK_PORT}..."
    if lsof -ti:"${SLACK_PORT}" >/dev/null 2>&1; then
        echo "❌ Slack server is already running on port ${SLACK_PORT}."
        echo "💡 Use --restart to force restart existing server."
        echo "💡 Use --help for more options."
        exit 1
    fi
    echo "✅ No existing Slack server found."
fi

# Check if Goose server is running
echo "Checking if Goose task server is running..."
if ! curl -s "http://localhost:8765/health" >/dev/null 2>&1; then
    echo "❌ Goose task server is not running on http://localhost:8765"
    echo "💡 Start Goose services first with: ./scripts/start_server.sh"
    exit 1
fi
echo "✅ Goose task server is running."

# Activate virtual environment
echo "Activating virtual environment..."
source "${SCRIPT_DIR}/.venv/bin/activate"

# Set environment variables
export GOOSE_SERVER_URL="${GOOSE_SERVER_URL:-http://localhost:8765}"

# Ensure .logs directory exists
mkdir -p "${SCRIPT_DIR}/.logs"

# Start Slack middleware server in background
echo "Starting Slack middleware server on port ${SLACK_PORT}..."
PORT="${SLACK_PORT}" PYTHONPATH="${SCRIPT_DIR}" python "${SCRIPT_DIR}/src/services/slack_server.py" > "${SCRIPT_DIR}/.logs/slack_server.log" 2>&1 &
SLACK_PID=$!

# Wait a moment for server to start
sleep 2

# Check if server started successfully
if kill -0 "$SLACK_PID" 2>/dev/null; then
    echo ""
    echo "Slack middleware server started successfully!"
    echo "  Server PID: ${SLACK_PID}"
    echo "  Server URL: http://localhost:${SLACK_PORT}"
    echo "  Slack endpoint: http://localhost:${SLACK_PORT}/slack/command"
    echo ""
    echo "Logs: ${SCRIPT_DIR}/.logs/slack_server.log"
    echo ""
    echo "To expose this server to Slack:"
    echo "  1. Install ngrok: https://ngrok.com/download"
    echo "  2. Run: ngrok http ${SLACK_PORT}"
    echo "  3. Copy the ngrok URL to your Slack app's slash command Request URL"
    echo "  4. Configure your slash command (e.g., /goose) in Slack"
    echo ""
    echo "To stop the server:"
    echo "  kill ${SLACK_PID}"
    echo "  # or: lsof -ti:${SLACK_PORT} | xargs kill -9"
    echo ""
    echo "Server is running in the background."
else
    echo "❌ Failed to start Slack middleware server. Check logs: ${SCRIPT_DIR}/.logs/slack_server.log"
    exit 1
fi