# Skein

Goals:
- To wrap [Goose](https://github.com/block/goose) in a RESTful server in order to call it from Slack and other products.
- To have a broader selection of models
- To make it easy to add tools
- To have more ways of using Goose

## Files

- `setup.sh` - install and configure everything
- `start_server.sh` - start both LiteLLM proxy and Goose task server
- `stop_server.sh` - stop both LiteLLM proxy and Goose task server
- `start_prompt.sh` - interactive prompt for submitting tasks
- `litellm_config.yaml` - LiteLLM model mapping.
- `goose_config.yaml` - Local Goose configuration for the task server
- `goose_task.py` - CLI script to submit tasks and optionally wait for completion

## 1) Setup

```bash
cd agents-goose
chmod +x setup.sh
./setup.sh
```

If needed, configure AWS credentials:

```bash
aws configure
```

I haven't played with the other major clouds yet.

## 2) Run services

### Option 1: Automated startup script (recommended)

```bash
cd agents-goose
./start_server.sh
```

This script will automatically:
- Kill any existing processes on ports 4321 and 8765 (restart mode, default)
- Activate the virtual environment
- Start both LiteLLM proxy and Goose task server in the background
- Display PIDs and stop commands

#### Options:
- `--restart` (default): Restart services if already running
- `--no-restart`: Only start services if they're not already running
- `--help`: Show usage information

#### Examples:
```bash
./start_server.sh              # Start/restart services (default)
./start_server.sh --restart    # Same as default
./start_server.sh --no-restart # Only start if not running
```

### Stopping services

```bash
cd agents-goose
./stop_server.sh
```

This script will:
- Stop both LiteLLM proxy and Goose task server
- Report success/failure status
- Handle cases where services are already stopped

### Interactive task prompt

```bash
cd agents-goose
./start_prompt.sh
```

This starts an interactive session where you can submit tasks without leaving the terminal:

```
goose> task "Write a hello world program in Python"
goose> task mytask.md
goose> help
goose> quit
```

Available commands:
- `task "your task here"` - Submit a task as text
- `task filename.md` - Submit a task from a markdown file
- `help` - Show available commands
- `quit`/`exit`/`q` - Exit the interactive session

### Option 2: Manual startup

## Run test client

```bash
cd agents-goose
source .venv/bin/activate
python goose_task.py --task "Write a hello world program in Python" --wait
```

You can optionally specify a different model (defaults to `bedrock-claude-opus-4-6`):

```bash
python goose_task.py --task "Write a hello world program" --model bedrock-claude-opus-4-6 --wait
```

It submits the task, waits for completion, and shows the final status and output.

## API

- `GET /health`: Health check endpoint
- `GET /models`: Get available models from LiteLLM
- `POST /tasks` with body:

```json
{
  "task": "Write exactly one line: Hello, world!",
  "model": "bedrock-claude-opus-4-6"
}
```

- `GET /tasks`: List all tasks
- `GET /tasks/<task_id>`: Get specific task status (`queued`, `running`, `completed`, `failed`) and output

Example usage with Python client:

```python
from goose_client import GooseTaskClient

client = GooseTaskClient()

# Get available models
models = client.get_models()
print("Available models:", [m["id"] for m in models])

# Submit a task
response = client.submit_task("Create a hello.py file", model="bedrock-claude-opus-4-6")
task_id = response["task_id"]

# Wait for completion
result = client.wait_for_done(task_id)
print("Task result:", result)
```
