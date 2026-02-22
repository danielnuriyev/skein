# Goose Task Server

This project runs Goose behind a local HTTP task server.

The goal is to call this server from Slack and other applications.

## Files

- `setup.sh` - install and configure everything
- `litellm_config.yaml` - LiteLLM model mapping.
- `goose_server.py` - local HTTP task server
- `goose_client.py` - Python client (`submit_task`, `get_task_status`)
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

## 2) Run services

Terminal 1 (LiteLLM proxy):

```bash
cd agents-goose
source .venv/bin/activate
litellm --config litellm_config.yaml --port 4321
```

Terminal 2 (task server):

```bash
cd agents-goose
source .venv/bin/activate
python goose_server.py
```

## 3) Run test client

Terminal 3:

```bash
cd agents-goose
source .venv/bin/activate
python goose_task.py --task "Write a hello world program in Python" --wait
```

You can optionally specify a different model (defaults to `bedrock-nova-lite`):

```bash
python goose_task.py --task "Write a hello world program" --model bedrock-nova-pro --wait
```

It submits the task, waits for completion, and shows the final status and output.

## API

- `POST /tasks` with body:

```json
{
  "task": "Write exactly one line: Hello, world!",
  "model": "bedrock-nova-lite"
}
```

- `GET /tasks/<task_id>` returns task status (`queued`, `running`, `completed`, `failed`) and output.

## Notes

- Goose config is written to `~/.config/goose/config.yaml` by `setup.sh`.
- Required keys are uppercase: `GOOSE_PROVIDER`, `GOOSE_MODEL`, `LITELLM_HOST`, `LITELLM_BASE_PATH`.
