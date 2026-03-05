#!/bin/bash

# Start script for Slack Events Handler
# This script starts the Slack events subscription server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default values
RESTART_SERVICES=true
SLACK_EVENTS_PORT=3001

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
            SLACK_EVENTS_PORT="$2"
            shift
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Start Slack Events Handler for @mention integration."
            echo ""
            echo "Options:"
            echo "  --restart         Restart server if already running (default)"
            echo "  --no-restart      Don't restart server if already running"
            echo "  --port PORT       Port to run events server on (default: 3001)"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  SLACK_SIGNING_SECRET    Required for request verification"
            echo "  SLACK_BOT_TOKEN         Required for sending responses"
            echo "  GOOSE_SERVER_URL        URL of goose_server.py (default: http://localhost:8765)"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start server (restart if running)"
            echo "  $0 --no-restart              # Start server only if not running"
            echo "  $0 --port 8080               # Start on port 8080"
            echo ""
            echo "For Slack Events setup:"
            echo "  1. Create a Slack App at https://api.slack.com/apps"
            echo "  2. Enable Event Subscriptions"
            echo "  3. Set Request URL to: https://your-domain.ngrok.io/events"
            echo "  4. Subscribe to: app_mention, message.im"
            echo "  5. Add OAuth scope: chat:write"
            echo "  6. Use ngrok to expose port ${SLACK_EVENTS_PORT}: ngrok http ${SLACK_EVENTS_PORT}"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

echo "Starting Slack Events Handler..."

# Kill existing process on the specified port if restart is enabled
if [ "$RESTART_SERVICES" = true ]; then
    echo "Checking for existing processes on port ${SLACK_EVENTS_PORT}..."
    lsof -ti:"${SLACK_EVENTS_PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
else
    echo "Checking if Slack events server is already running on port ${SLACK_EVENTS_PORT}..."
    if lsof -ti:"${SLACK_EVENTS_PORT}" >/dev/null 2>&1; then
        echo "❌ Slack events server is already running on port ${SLACK_EVENTS_PORT}."
        echo "💡 Use --restart to force restart existing server."
        echo "💡 Use --help for more options."
        exit 1
    fi
    echo "✅ No existing Slack events server found."
fi

# Check if Goose server is running
echo "Checking if Goose task server is running..."
if ! curl -s "http://localhost:8765/health" >/dev/null 2>&1; then
    echo "❌ Goose task server is not running on http://localhost:8765"
    echo "💡 Start Goose services first with: ./scripts/start_server.sh"
    exit 1
fi
echo "✅ Goose task server is running."

# Check required environment variables
if [ -z "${SLACK_SIGNING_SECRET:-}" ]; then
    echo "⚠️  WARNING: SLACK_SIGNING_SECRET is not set!"
    echo "   Event verification will be disabled (not recommended for production)"
    echo "   Set it with: export SLACK_SIGNING_SECRET='your-secret'"
fi

if [ -z "${SLACK_BOT_TOKEN:-}" ]; then
    echo "⚠️  WARNING: SLACK_BOT_TOKEN is not set!"
    echo "   The bot will not be able to send responses back to Slack"
    echo "   Set it with: export SLACK_BOT_TOKEN='xoxb-your-token'"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "${SCRIPT_DIR}/.venv/bin/activate"

# Ensure .logs directory exists
mkdir -p "${SCRIPT_DIR}/.logs"

# Start Slack events server in background
echo "Starting Slack Events Handler on port ${SLACK_EVENTS_PORT}..."
PORT="${SLACK_EVENTS_PORT}" PYTHONPATH="${SCRIPT_DIR}" python "${SCRIPT_DIR}/src/services/slack_events.py" > "${SCRIPT_DIR}/.logs/slack_events.log" 2>&1 &
SLACK_EVENTS_PID=$!

# Wait a moment for server to start
sleep 2

# Check if server started successfully
if kill -0 "$SLACK_EVENTS_PID" 2>/dev/null; then
    echo ""
    echo "Slack Events Handler started successfully!"
    echo "  Server PID: ${SLACK_EVENTS_PID}"
    echo "  Server URL: http://localhost:${SLACK_EVENTS_PORT}"
    echo "  Events endpoint: http://localhost:${SLACK_EVENTS_PORT}/events"
    echo ""
    echo "Logs: ${SCRIPT_DIR}/.logs/slack_events.log"
    echo ""
    echo "To expose this server to Slack:"
    echo "  1. Install ngrok: https://ngrok.com/download"
    echo "  2. Run: ngrok http ${SLACK_EVENTS_PORT}"
    echo "  3. Configure Event Subscriptions in your Slack app:"
    echo "     - Request URL: https://your-ngrok-url.ngrok.io/events"
    echo "     - Subscribe to: app_mention, message.im"
    echo ""
    echo "Users can now mention your bot: @YourBotName <task description>"
    echo ""
    echo "To stop the server:"
    echo "  kill ${SLACK_EVENTS_PID}"
    echo "  # or: lsof -ti:${SLACK_EVENTS_PORT} | xargs kill -9"
    echo ""
    echo "Server is running in the background."
else
    echo "❌ Failed to start Slack Events Handler. Check logs: ${SCRIPT_DIR}/.logs/slack_events.log"
    exit 1
fi