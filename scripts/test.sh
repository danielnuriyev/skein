#!/bin/bash

# Comprehensive testing script for Python code
# Runs pytest with parallel execution and coverage

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to run tests with specific options
run_tests() {
    local test_type="$1"
    local extra_args="$2"

    echo -e "${YELLOW}Running ${test_type} tests...${NC}"

    if python -m pytest \
        --tb=short \
        --strict-markers \
        --disable-warnings \
        $extra_args; then

        echo -e "${GREEN}✅ ${test_type} tests passed${NC}"
        return 0
    else
        local exit_code=$?
        echo -e "${RED}❌ ${test_type} tests failed (exit code: ${exit_code})${NC}"
        return 1
    fi
}

# Parse command line arguments
RUN_ALL=true
RUN_UNIT=false
RUN_INTEGRATION=false
RUN_PERFORMANCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_ALL=false
            RUN_UNIT=true
            shift
            ;;
        --integration)
            RUN_ALL=false
            RUN_INTEGRATION=true
            shift
            ;;
        --performance)
            RUN_ALL=false
            RUN_PERFORMANCE=true
            shift
            ;;
        --no-cov)
            # Disable coverage for faster runs
            export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Run comprehensive tests for the Python codebase."
            echo ""
            echo "Options:"
            echo "  --unit          Run only unit tests"
            echo "  --integration   Run only integration tests"
            echo "  --performance   Run only performance tests"
            echo "  --no-cov        Skip coverage reporting for faster runs"
            echo "  --help, -h      Show this help message"
            echo ""
            echo "By default, runs all tests with coverage."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🧪 Running comprehensive test suite...${NC}"
echo

# Change to project directory
cd "${PROJECT_DIR}"

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source .venv/bin/activate

echo

# Determine CPU count for parallel execution
CPU_COUNT=$(python -c "import os; print(os.cpu_count() or 4)")
echo -e "${BLUE}Using ${CPU_COUNT} parallel processes${NC}"
echo

# Track failures
FAILED_TESTS=0

# Run different test types
if [ "$RUN_ALL" = true ] || [ "$RUN_UNIT" = true ]; then
    if run_tests "unit" "-m unit"; then
        echo
    else
        ((FAILED_TESTS++))
    fi
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_INTEGRATION" = true ]; then
    if run_tests "integration" "-m integration"; then
        echo
    else
        ((FAILED_TESTS++))
    fi
fi

if [ "$RUN_ALL" = true ] || [ "$RUN_PERFORMANCE" = true ]; then
    if run_tests "performance" "-m performance"; then
        echo
    else
        ((FAILED_TESTS++))
    fi
fi

# Run all tests if no specific type requested
if [ "$RUN_ALL" = true ]; then
    if run_tests "all" ""; then
        echo
    else
        ((FAILED_TESTS++))
    fi
fi

# Summary
echo -e "${BLUE}📊 Test Summary:${NC}"

if [ ${FAILED_TESTS} -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"

    # Show coverage report if available
    if [ -f "htmlcov/index.html" ]; then
        echo "Coverage report: htmlcov/index.html"
    fi

    exit 0
else
    echo -e "${RED}💥 ${FAILED_TESTS} test suite(s) failed${NC}"
    echo
    echo -e "${YELLOW}💡 Debug failed tests:${NC}"
    echo "  python -m pytest --tb=long --pdb failed_tests/"
    echo "  python -m pytest --cov=src --cov-report=html failed_tests/"
    echo
    echo -e "${YELLOW}💡 Run specific tests:${NC}"
    echo "  ./scripts/test.sh --unit         # Run only unit tests"
    echo "  ./scripts/test.sh --integration  # Run only integration tests"
    echo "  ./scripts/test.sh --performance  # Run only performance tests"
    exit 1
fi