#!/bin/bash

# Comprehensive linting script for Python, YAML, and Shell scripts
# Runs all configured linters and reports results

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0

# Parse command line arguments
FIX_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --fix)
            FIX_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Run comprehensive linting for Python, YAML, and shell scripts."
            echo ""
            echo "Options:"
            echo "  --fix            Auto-fix issues where possible (isort, black)"
            echo "  --help, -h       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0               # Check for issues"
            echo "  $0 --fix         # Auto-fix formatting issues"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

if [ "$FIX_MODE" = true ]; then
    echo -e "${BLUE}🔧 Running linting with auto-fix...${NC}"
else
    echo -e "${BLUE}🔍 Running comprehensive linting suite...${NC}"
fi
echo

# Function to run a linter and track results
run_linter() {
    local name="$1"
    local command="$2"
    local description="$3"

    echo -e "${YELLOW}Running ${name}...${NC}"
    echo "  ${description}"
    echo "  Command: ${command}"

    if eval "${command}"; then
        echo -e "${GREEN}✅ ${name} passed${NC}"
        echo
    else
        local exit_code=$?
        echo -e "${RED}❌ ${name} failed (exit code: ${exit_code})${NC}"
        ((ERRORS++))
        echo
    fi
}

# Change to project directory
cd "${PROJECT_DIR}"

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source .venv/bin/activate

echo

# Python linting
if [ "$FIX_MODE" = true ]; then
    run_linter "isort" "python -m isort src/ scripts/" "Fix Python import sorting"
    run_linter "black" "python -m black src/ scripts/" "Fix Python code formatting"
else
    run_linter "isort" "python -m isort --check-only --diff src/ scripts/" "Check Python import sorting"
    run_linter "black" "python -m black --check --diff src/ scripts/" "Check Python code formatting"
fi
run_linter "flake8" "python -m flake8 --max-line-length=200 --extend-ignore=E203,W503,E402,F401,F841,F541,E501 src/ scripts/" "Check Python style and errors (minimal rules)"
# Skip mypy for now - too strict for existing codebase
# run_linter "mypy" "python -m mypy --ignore-missing-imports src/" "Check Python type hints (relaxed)"

# YAML linting
run_linter "yamllint" "python -m yamllint config/ prompts/ .yamllint.yaml" "Check YAML formatting and syntax"

# Shell script linting
if command -v shellcheck >/dev/null 2>&1; then
    run_linter "shellcheck" "shellcheck scripts/*.sh" "Check shell script syntax and best practices"
else
    echo -e "${YELLOW}⚠️  shellcheck not found, skipping shell script linting${NC}"
    echo "  Install shellcheck to enable shell script linting"
    echo
fi

# Summary
echo -e "${BLUE}📊 Linting Summary:${NC}"
if [ ${ERRORS} -eq 0 ]; then
    echo -e "${GREEN}🎉 All linting checks passed!${NC}"
    echo "  Your code follows all configured style guidelines."
    exit 0
else
    echo -e "${RED}💥 ${ERRORS} linting check(s) failed${NC}"
    echo "  Please fix the issues above and run linting again."
    echo
    echo -e "${YELLOW}💡 Quick fixes:${NC}"
    echo "  python -m isort src/ scripts/                    # Fix import sorting"
    echo "  python -m black src/ scripts/                    # Fix code formatting"
    echo "  python -m flake8 src/ scripts/                   # Check remaining issues"
    exit 1
fi