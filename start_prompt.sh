#!/bin/bash

# Interactive prompt for submitting Goose tasks
# Provides a REPL-like interface for task submission and monitoring

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "${SCRIPT_DIR}/.venv/bin/activate"

# Check if services are running
echo -e "${BLUE}Checking if Goose services are running...${NC}"
if ! curl -s http://localhost:8765/health >/dev/null 2>&1; then
    echo -e "${RED}❌ Goose task server is not running on http://localhost:8765${NC}"
    echo -e "${YELLOW}💡 Start services first with: ./start_server.sh${NC}"
    exit 1
fi

if ! curl -s http://localhost:4321/health >/dev/null 2>&1; then
    echo -e "${RED}❌ LiteLLM proxy is not running on http://localhost:4321${NC}"
    echo -e "${YELLOW}💡 Start services first with: ./start_server.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Services are running. Starting interactive session...${NC}"
echo ""

# Enable bash history for the interactive prompt
HISTFILE=~/.goose_prompt_history
HISTSIZE=1000
set -o history
history -r "$HISTFILE" 2>/dev/null || true

# Format prompt with readline non-printing character escapes for correct arrow-key navigation
PROMPT=$'\001\e[0;34m\002goose>\001\e[0m\002 '

# Interactive loop
while true; do
    read -e -p "$PROMPT" input

    # Handle empty input
    if [ -z "$input" ]; then
        continue
    fi

    # Save to history
    history -s "$input"
    history -w "$HISTFILE"

    # Parse command
    command=$(echo "$input" | awk '{print $1}')
    args=$(echo "$input" | cut -d' ' -f2-)

    case "$command" in
        "quit"|"exit"|"q")
            echo -e "${GREEN}👋 Goodbye!${NC}"
            exit 0
            ;;
        "task")
            if [ -z "$args" ]; then
                echo -e "${RED}❌ Usage: task \"your task here\" or task filename.md${NC}"
                continue
            fi

            # Check if it's a file or direct text
            if [[ "$args" == *.md ]] || [[ "$args" == *.txt ]] || [[ "$args" == *.markdown ]]; then
                # It's a file - expand ~ to home directory
                expanded_path=$(echo "$args" | sed "s|^~|$HOME|")
                if [ ! -f "$expanded_path" ]; then
                    echo -e "${RED}❌ File not found: $args${NC}"
                    continue
                fi
                echo -e "${YELLOW}📄 Submitting task from file: $args${NC}"
                python "${SCRIPT_DIR}/goose_task.py" --task-file "$expanded_path" --wait
            else
                # It's direct text (should be quoted)
                if [[ "$args" != \"*\" ]]; then
                    echo -e "${RED}❌ Text tasks must be quoted: task \"your task here\"${NC}"
                    continue
                fi
                # Remove surrounding quotes
                task_text=$(echo "$args" | sed 's/^"\(.*\)"$/\1/')
                echo -e "${YELLOW}💬 Submitting task: $task_text${NC}"
                python "${SCRIPT_DIR}/goose_task.py" --task "$task_text" --wait
            fi
            echo ""
            ;;
        "help"|"?")
            echo -e "${BLUE}Available commands:${NC}"
            echo "  task \"your task here\"    - Submit a task as text"
            echo "  task filename.md          - Submit a task from a markdown file"
            echo "  help                      - Show this help"
            echo "  quit/exit/q               - Exit the interactive session"
            echo ""
            ;;
        *)
            echo -e "${RED}❌ Unknown command: $command${NC}"
            echo -e "${YELLOW}💡 Type 'help' for available commands${NC}"
            echo ""
            ;;
    esac
done