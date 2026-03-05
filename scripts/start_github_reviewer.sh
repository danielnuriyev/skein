#!/bin/bash

# Start script for GitHub PR Reviewer
# This script starts the GitHub webhook server for PR reviews

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default values
RESTART_SERVICES=true
GITHUB_PORT=4000

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
            GITHUB_PORT="$2"
            shift
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Start GitHub PR Reviewer for automated code reviews."
            echo ""
            echo "Options:"
            echo "  --restart         Restart server if already running (default)"
            echo "  --no-restart      Don't restart server if already running"
            echo "  --port PORT       Port to run reviewer server on (default: 4000)"
            echo "  --help, -h        Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  GITHUB_WEBHOOK_SECRET    Required for webhook verification"
            echo "  GITHUB_TOKEN             Required for posting reviews"
            echo "  GOOSE_SERVER_URL         URL of goose_server.py (default: http://localhost:8765)"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start server (restart if running)"
            echo "  $0 --no-restart              # Start server only if not running"
            echo "  $0 --port 8080               # Start on port 8080"
            echo ""
            echo "For GitHub setup:"
            echo "  1. Go to repository Settings → Webhooks"
            echo "  2. Add webhook: https://your-domain.ngrok.io/webhook"
            echo "  3. Content type: application/json"
            echo "  4. Events: Pull requests"
            echo "  5. Add webhook secret for verification"
            echo "  6. Use ngrok to expose port ${GITHUB_PORT}: ngrok http ${GITHUB_PORT}"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

echo "Starting GitHub PR Reviewer..."

# Kill existing process on the specified port if restart is enabled
if [ "$RESTART_SERVICES" = true ]; then
    echo "Checking for existing processes on port ${GITHUB_PORT}..."
    lsof -ti:"${GITHUB_PORT}" | xargs kill -9 2>/dev/null || true
    sleep 1
else
    echo "Checking if GitHub reviewer is already running on port ${GITHUB_PORT}..."
    if lsof -ti:"${GITHUB_PORT}" >/dev/null 2>&1; then
        echo "❌ GitHub reviewer is already running on port ${GITHUB_PORT}."
        echo "💡 Use --restart to force restart existing server."
        echo "💡 Use --help for more options."
        exit 1
    fi
    echo "✅ No existing GitHub reviewer found."
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
if [ -z "${GITHUB_WEBHOOK_SECRET:-}" ]; then
    echo "⚠️  WARNING: GITHUB_WEBHOOK_SECRET is not set!"
    echo "   Webhook verification will be disabled (not recommended for production)"
    echo "   Set it with: export GITHUB_WEBHOOK_SECRET='your-webhook-secret'"
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "⚠️  WARNING: GITHUB_TOKEN is not set!"
    echo "   The reviewer will not be able to post reviews to GitHub"
    echo "   Create a token at: https://github.com/settings/tokens"
    echo "   Set it with: export GITHUB_TOKEN='ghp_your_token'"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "${SCRIPT_DIR}/../.venv/bin/activate"

# Ensure .logs directory exists
mkdir -p "${SCRIPT_DIR}/../.logs"

# Start GitHub reviewer server in background
echo "Starting GitHub PR Reviewer on port ${GITHUB_PORT}..."
PORT="${GITHUB_PORT}" PYTHONPATH="${SCRIPT_DIR}" python "${SCRIPT_DIR}/src/services/github_pr_reviewer.py" > "${SCRIPT_DIR}/.logs/github_reviewer.log" 2>&1 &
GITHUB_PID=$!

# Wait a moment for server to start
sleep 2

# Check if server started successfully
if kill -0 "$GITHUB_PID" 2>/dev/null; then
    echo ""
    echo "GitHub PR Reviewer started successfully!"
    echo "  Server PID: ${GITHUB_PID}"
    echo "  Server URL: http://localhost:${GITHUB_PORT}"
    echo "  Webhook endpoint: http://localhost:${GITHUB_PORT}/webhook"
    echo ""
    echo "Logs: ${SCRIPT_DIR}/.logs/github_reviewer.log"
    echo ""
    echo "To expose this server to GitHub:"
    echo "  1. Install ngrok: https://ngrok.com/download"
    echo "  2. Run: ngrok http ${GITHUB_PORT}"
    echo "  3. Add webhook in GitHub repo Settings:"
    echo "     - URL: https://your-ngrok-url.ngrok.io/webhook"
    echo "     - Content type: application/json"
    echo "     - Events: Pull requests"
    echo "     - Secret: ${GITHUB_WEBHOOK_SECRET:-<not set>}"
    echo ""
    echo "The reviewer will automatically review PRs when opened/updated!"
    echo ""
    echo "To stop the server:"
    echo "  kill ${GITHUB_PID}"
    echo "  # or: lsof -ti:${GITHUB_PORT} | xargs kill -9"
    echo ""
    echo "Server is running in the background."
else
    echo "❌ Failed to start GitHub PR Reviewer. Check logs: ${SCRIPT_DIR}/.logs/github_reviewer.log"
    exit 1
fi