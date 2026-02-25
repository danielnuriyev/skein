#!/bin/bash

# Start script for Goose Task Server and LiteLLM proxy
# This script activates the virtual environment and starts both services

set -euo pipefail

# Default values
RESTART_SERVICES=true

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
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Start Goose Task Server and LiteLLM proxy services."
            echo ""
            echo "Options:"
            echo "  --restart      Restart services if already running (default)"
            echo "  --no-restart   Don't restart services if already running"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0              # Start services (restart if running)"
            echo "  $0 --no-restart # Start services only if not running"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Starting Goose Task Server services..."

# Kill any existing processes on the required ports if restart is enabled
if [ "$RESTART_SERVICES" = true ]; then
    echo "Checking for existing processes on ports 4321 and 8765..."
    lsof -ti:4321,8765 | xargs kill -9 2>/dev/null || true
    sleep 1
else
    echo "Checking if services are already running..."
    if lsof -ti:4321,8765 >/dev/null 2>&1; then
        echo "❌ Services are already running on ports 4321 and 8765."
        echo "💡 Use --restart to force restart existing services."
        echo "💡 Use --help for more options."
        exit 1
    fi
    echo "✅ No existing services found."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "${SCRIPT_DIR}/.venv/bin/activate"

# Ensure TLS trust store is available for outbound HTTPS calls (e.g., LiteLLM model cost map fetch)
CERT_PATH="$(python -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
if [ -n "${CERT_PATH}" ] && [ -f "${CERT_PATH}" ]; then
    export SSL_CERT_FILE="${CERT_PATH}"
    export REQUESTS_CA_BUNDLE="${CERT_PATH}"
fi

# Avoid external GitHub fetch for model-cost map; use packaged local map.
export LITELLM_LOCAL_MODEL_COST_MAP=True

# Ensure .logs directory exists
mkdir -p "${SCRIPT_DIR}/.logs"

# Start LiteLLM proxy in background
echo "Starting LiteLLM proxy on port 4321..."
litellm --config "${SCRIPT_DIR}/litellm_config.yaml" --port 4321 > "${SCRIPT_DIR}/.logs/litellm.log" 2>&1 &
LITELLM_PID=$!

# Wait a moment for LiteLLM to start
sleep 3

# Start Goose task server in background
echo "Starting Goose task server on port 8765..."
python "${SCRIPT_DIR}/goose_server.py" > "${SCRIPT_DIR}/.logs/goose_server.log" 2>&1 &
GOOSE_PID=$!

# Wait a moment for services to fully start
sleep 2

echo ""
echo "Services started successfully!"
echo "  LiteLLM proxy (PID: ${LITELLM_PID}): http://localhost:4321"
echo "  Goose server (PID: ${GOOSE_PID}): http://localhost:8765"
echo ""
echo "Logs are being written to:"
echo "  ${SCRIPT_DIR}/.logs/litellm.log"
echo "  ${SCRIPT_DIR}/.logs/goose_server.log"
echo ""
echo "To stop services:"
echo "  kill ${LITELLM_PID} ${GOOSE_PID}"
echo "  # or: lsof -ti:4321,8765 | xargs kill -9"
echo ""
echo "Services are running in the background. You can close this terminal."