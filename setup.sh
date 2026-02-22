#!/bin/bash

# One-shot setup for Goose + LiteLLM

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
PYTHON_VERSION="3.12"

echo "Setting up Goose with LiteLLM proxy for Bedrock Claude 4.6 Opus..."

if ! command -v curl >/dev/null 2>&1; then
  echo "Error: curl is required but was not found."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf "https://astral.sh/uv/install.sh" | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v goose >/dev/null 2>&1; then
  echo "Installing Goose CLI..."
  curl -fsSL "https://github.com/block/goose/releases/download/stable/download_cli.sh" | bash
else
  echo "Goose CLI already installed."
fi

RECREATE_VENV=0
if [ -d "${VENV_DIR}" ]; then
  VENV_PY_VER="$("${VENV_DIR}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  # Python 3.9 is too old (causes LiteLLM guardrail errors), Python 3.14 is too new (uvloop errors).
  if [ "${VENV_PY_VER}" != "${PYTHON_VERSION}" ]; then
    RECREATE_VENV=1
  fi
fi

if [ ! -d "${VENV_DIR}" ] || [ "${RECREATE_VENV}" -eq 1 ]; then
  if [ "${RECREATE_VENV}" -eq 1 ]; then
    echo "Recreating .venv to use Python ${PYTHON_VERSION}..."
    rm -rf "${VENV_DIR}"
  else
    echo "Creating Python virtual environment..."
  fi
  uv venv --python "${PYTHON_VERSION}" "${VENV_DIR}"
fi

echo "Installing LiteLLM dependencies in .venv..."
uv pip install -q --python "${VENV_DIR}/bin/python" "litellm[proxy]" boto3 python-multipart

if [ ! -f "${HOME}/.aws/credentials" ]; then
  echo "Warning: ${HOME}/.aws/credentials not found."
  echo "Run 'aws configure' before making model calls."
else
  echo "AWS credentials file found."
fi

echo ""
echo "Setup complete. Run these commands:"
echo ""
echo "Terminal 1:"
echo "  cd \"${SCRIPT_DIR}\""
echo "  source .venv/bin/activate"
echo "  litellm --config litellm_config.yaml --port 4321"
echo ""
echo "Terminal 2:"
echo "  cd \"${SCRIPT_DIR}\""
echo "  source .venv/bin/activate"
echo "  python goose_server.py"
echo ""
echo "Terminal 3 (example test):"
echo "  cd \"${SCRIPT_DIR}\""
echo "  source .venv/bin/activate"
echo "  python goose_task.py --task \"Write a hello world program in Python\" --wait"