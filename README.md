# Skein

Goals:
- To wrap [Goose](https://github.com/block/goose) in a RESTful server in order to call it from Slack and other products.
- To have a broader selection of models
- To make it easy to add tools
- To have more ways of using Goose

## Files

- `scripts/setup.sh` - install and configure everything
- `scripts/start_server.sh` - start both LiteLLM proxy and Goose task server
- `scripts/stop_server.sh` - stop both LiteLLM proxy and Goose task server
- `scripts/start_prompt.sh` - interactive prompt for submitting tasks
- `src/` - Python source code directory
  - `slack_server.py` - Bottle middleware server for Slack slash commands (/goose)
  - `slack_events.py` - Bottle server for Slack Event Subscriptions (@mentions, messages)
  - `github_pr_reviewer.py` - Bottle server for GitHub PR webhook reviews
  - `dagster_tool.py` - Python tool for Dagster pipeline operations
  - `glue_tool.py` - Python tool for AWS Glue interactions
  - `athena_tool.py` - Python tool for AWS Athena interactions
  - `trino_tool.py` - Python tool for Trino interactions
  - `datahub_tool.py` - Python tool for DataHub interactions
  - `goose_server.py` - HTTP server for Goose task management
  - `goose_client.py` - Python client for the Goose server API
  - `goose_task.py` - CLI script to submit tasks and optionally wait for completion
- `scripts/start_slack_server.sh` - start Slack middleware server for slash commands (/goose)
- `scripts/start_slack_events.sh` - start Slack Events Handler for @mention integration
- `scripts/start_github_reviewer.sh` - start GitHub PR Reviewer for automated code reviews
  - `scripts/lint.sh` - run comprehensive linting for Python, YAML, and shell scripts
  - `scripts/test.sh` - run comprehensive testing with pytest
  - `scripts/example_dagster_usage.py` - example script demonstrating Dagster tool usage
  - `scripts/deploy-k8s.sh` - deploy entire ecosystem to Kubernetes
  - `scripts/start-k8s.sh` - start all Kubernetes services
  - `scripts/stop-k8s.sh` - stop all Kubernetes services
  - `scripts/monitor-k8s.sh` - monitor all Kubernetes services
- `config/` - Configuration files directory
  - `litellm_config.yaml` - LiteLLM model mapping
  - `goose_config.yaml` - Local Goose configuration for the task server
- `prompts/` - Prompt templates directory
  - `github_pr_reviewer.md` - Review guidelines template for GitHub PR reviews

## 1) Setup

```bash
cd agents-goose
chmod +x setup.sh
./scripts/setup.sh
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
./scripts/start_server.sh
```

This script will automatically:
- Kill any existing processes on ports 4321 and 8765 (restart mode, default)
- Activate the virtual environment
- Start both LiteLLM proxy and Goose task server in the background
- Display PIDs and stop commands

AWS credential behavior:
- `start_server.sh` uses profile-based AWS auth (`AWS_PROFILE`, default `default`)
- It clears static `AWS_*KEY*` env vars before launching LiteLLM
- Use refreshable profile credentials (for example SSO/credential_process) for best no-restart behavior

#### Options:
- `--restart` (default): Restart services if already running
- `--no-restart`: Only start services if they're not already running
- `--help`: Show usage information

#### Examples:
```bash
./scripts/start_server.sh              # Start/restart services (default)
./scripts/start_server.sh --restart    # Same as default
./scripts/start_server.sh --no-restart # Only start if not running
```

### Stopping services

```bash
cd agents-goose
./scripts/stop_server.sh
```

This script will:
- Stop both LiteLLM proxy and Goose task server
- Report success/failure status
- Handle cases where services are already stopped

### Interactive task prompt

```bash
cd agents-goose
./scripts/start_prompt.sh
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

### Slack integration

```bash
cd agents-goose
./scripts/start_slack_server.sh
```

This starts a middleware server that bridges Slack slash commands to Goose tasks.
The server uses Bottle (a lightweight WSGI micro-framework) for minimal dependencies and fast performance.

#### Setup steps:

1. **Start the Slack server:**
   ```bash
   ./scripts/start_slack_server.sh              # Start on port 3000 (default)
   ./scripts/start_slack_server.sh --port 8080  # Start on custom port
   ```

2. **Expose the server publicly:**
   ```bash
   # Install ngrok from https://ngrok.com/download
   ngrok http 3000
   ```
   Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)

3. **Create a Slack App:**
   - Go to [https://api.slack.com/apps](https://api.slack.com/apps)
   - Click "Create New App" → "From scratch"
   - Name your app (e.g., "Goose Bot") and select your workspace

4. **Add a Slash Command:**
   - In your Slack app, go to "Slash Commands" → "Create New Command"
   - Command: `/goose` (or your preferred command name)
   - Request URL: `https://your-ngrok-url.ngrok.io/slack/command`
   - Description: "Submit tasks to Goose AI agent"
   - Usage Hint: `<your task description>`

5. **Install the app to your workspace:**
   - Go to "OAuth & Permissions" → "Scopes"
   - Add `commands` scope
   - Go to "Install App" and install it to your workspace

#### Kubernetes Deployment URL:

If you're running the Slack server in Kubernetes, the URL will be different:

1. **Get the LoadBalancer external IP:**
   ```bash
   kubectl get services slack-server-service -n goose-system
   ```
   Look for the `EXTERNAL-IP` column.

2. **The complete slash command URL:**
   ```
   http://<EXTERNAL_IP>:3000/slack/command
   ```

3. **For local kind clusters:**
   If no external IP is available, use port forwarding:
   ```bash
   kubectl port-forward svc/slack-server-service 3000:3000 -n goose-system
   ```
   Then use `http://localhost:3000/slack/command` or expose with ngrok.

#### Usage:

In any Slack channel where the app is installed:
```
/goose Create a Python function to calculate fibonacci numbers
/goose Fix the bug in my code: the function returns None instead of the result
/goose Write a README for my project
```

The bot will:
- Immediately acknowledge your command
- Process the task asynchronously
- Send the results back to the channel when complete

#### Environment variables:

- `SLACK_SIGNING_SECRET`: For request verification (recommended for production)
- `GOOSE_SERVER_URL`: URL of src/goose_server.py (default: `http://localhost:8765`)

#### Troubleshooting:

- Ensure `./scripts/start_server.sh` is running first (starts Goose and LiteLLM)
- Check logs: `tail -f .logs/slack_server.log`
- Use `lsof -ti:3000 | xargs kill -9` to stop the Slack server

### Slack Events (Alternative to Slash Commands)

For a more interactive experience, you can set up Slack Event Subscriptions to allow users to mention the bot directly (@GooseBot) instead of using slash commands.

```bash
cd agents-goose
./scripts/start_slack_events.sh
```

This starts the events handler server that responds to @mentions and direct messages.

#### Setup steps:

1. **Start the events server:**
   ```bash
   ./scripts/start_slack_events.sh              # Start on port 3001 (default)
   ./scripts/start_slack_events.sh --port 8080  # Start on custom port
   ```

2. **Expose the server publicly:**
   ```bash
   # Install ngrok and expose the events endpoint
   ngrok http 3001
   ```
   Copy the ngrok URL (e.g., `https://def456.ngrok.io`)

3. **Configure Event Subscriptions:**
   - In your Slack App, go to "Event Subscriptions"
   - Enable Events
   - Set Request URL: `https://your-ngrok-url.ngrok.io/events`
   - Subscribe to bot events:
     - `app_mention` - When someone mentions @YourBotName
     - `message.im` - Direct messages to the bot (optional)

#### Kubernetes Deployment URL (Slack Events):

For Kubernetes deployments, use the LoadBalancer IP for the events endpoint:

```bash
# Get the events service external IP
kubectl get services slack-events-service -n goose-system

# The events URL will be:
http://<EXTERNAL_IP>:3001/events
```

For local clusters, use port forwarding:
```bash
kubectl port-forward svc/slack-events-service 3001:3001 -n goose-system
# Then use: http://localhost:3001/events
```

4. **Add Bot Token Scope:**
   - Go to "OAuth & Permissions" → "Scopes"
   - Add `chat:write` scope (to allow the bot to respond)
   - Reinstall the app to your workspace

#### Usage:

Users can now interact with the bot by mentioning it:

```
@GooseBot write a Python function to reverse a string
@GooseBot fix this bug: my function returns None
@GooseBot create a test file for my calculator class
```

**Advantages over slash commands:**
- More conversational (users can mention the bot naturally)
- Works in threads and conversations
- Supports direct messages
- Multiple interactions in the same channel

#### Environment variables:

- `SLACK_SIGNING_SECRET`: **Required** for request verification
- `SLACK_BOT_TOKEN`: **Required** for sending responses back to Slack
- `GOOSE_SERVER_URL`: URL of src/goose_server.py (default: `http://localhost:8765`)

#### Comparison:

| Feature | Slash Commands (/goose) | Event Subscriptions (@Bot) |
|---------|------------------------|---------------------------|
| **Setup complexity** | Simple | More complex (needs bot token) |
| **User experience** | Commands in any channel | Natural mentions, DMs |
| **Verification** | Optional | Required |
| **Response capability** | Via response_url | Via Web API (needs token) |
| **Cost** | Free | Free |
| **Best for** | Quick commands | Interactive conversations |

### GitHub PR Reviews (Automated Code Reviews)

For automated code review integration, you can set up GitHub webhooks to automatically review pull requests using Goose AI.

```bash
cd agents-goose
./scripts/start_github_reviewer.sh
```

This starts a webhook server that automatically reviews PRs when they are opened or updated.

#### Setup steps:

1. **Start the GitHub reviewer:**
   ```bash
   ./scripts/start_github_reviewer.sh              # Start on port 4000 (default)
   ./scripts/start_github_reviewer.sh --port 8080  # Start on custom port
   ```

2. **Expose the server publicly:**
   ```bash
   # Install ngrok and expose the webhook endpoint
   ngrok http 4000
   ```
   Copy the ngrok URL (e.g., `https://ghi789.ngrok.io`)

3. **Create a GitHub Personal Access Token:**
   - Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
   - Generate a new token with `repo` scope (for private repos) or `public_repo` (for public repos)
   - Copy the token

4. **Set up GitHub Webhook:**
   - Go to your repository **Settings → Webhooks**
   - Click **"Add webhook"**
   - **Payload URL:** `https://your-ngrok-url.ngrok.io/webhook`
   - **Content type:** `application/json`
   - **Secret:** Choose a webhook secret (save this for env var)
   - **Events:** Select "Pull requests"
   - Click **"Add webhook"**

#### Kubernetes Deployment URL (GitHub PR Reviewer):

For Kubernetes deployments, use the LoadBalancer IP for the webhook endpoint:

```bash
# Get the GitHub reviewer service external IP
kubectl get services github-pr-reviewer-service -n goose-system

# The webhook URL will be:
http://<EXTERNAL_IP>:4000/webhook
```

For local clusters, use port forwarding:
```bash
kubectl port-forward svc/github-pr-reviewer-service 4000:4000 -n goose-system
# Then use: http://localhost:4000/webhook
```

5. **Set Environment Variables:**
   ```bash
   export GITHUB_WEBHOOK_SECRET="your-webhook-secret"
   export GITHUB_TOKEN="ghp_your_github_token"
   ```

#### How it works:

When a PR is opened or updated, the webhook:
1. **Receives** the PR event from GitHub
2. **Fetches** the PR diff and details from GitHub API
3. **Submits** a comprehensive review request to Goose
4. **Posts** the AI-generated review back as a comment on the PR

#### Review Features:

- **Code Quality Analysis** - Identifies bugs, security issues, and best practices
- **Style & Documentation** - Reviews code style and documentation completeness
- **Error Handling** - Checks for proper error handling and edge cases
- **Performance Suggestions** - Identifies potential optimizations
- **Constructive Feedback** - Provides helpful, actionable suggestions
- **Line-Specific Comments** - Targets specific files and line numbers for actionable feedback
- **Comprehensive Overview** - Overall assessment with detailed breakdown

#### Example Review Output:

```
## 🤖 Goose AI Code Review

### Overall Assessment
The code demonstrates good structure and follows most best practices. The main areas for improvement are input validation and error handling.

### Code Quality
- The error handling in `process_data()` could be more specific
- Consider adding input validation for the `user_id` parameter

### Security Considerations
- Potential SQL injection vulnerability in query construction
- Consider using parameterized queries

### Suggestions
- Add docstrings to all public functions
- Consider breaking down `complex_function()` into smaller methods

---
*This review was generated automatically by Goose AI. Please consider the suggestions and implement improvements as appropriate.*
```

**Plus line-specific comments on individual files:**
- `src/main.py:15` - Consider adding input validation for the user_id parameter
- `tests/test_main.py:25` - Missing test case for edge condition

#### Environment variables:

- `GITHUB_WEBHOOK_SECRET`: **Required** - For webhook signature verification
- `GITHUB_TOKEN`: **Required** - For posting reviews and fetching PR data
- `GOOSE_SERVER_URL`: URL of src/goose_server.py (default: `http://localhost:8765`)

#### Troubleshooting:

- Ensure `./scripts/start_server.sh` is running first
- Check logs: `tail -f .logs/github_reviewer.log`
- Verify webhook secret matches the environment variable
- Test webhook delivery in GitHub repository settings
- Use `lsof -ti:4000 | xargs kill -9` to stop the reviewer

### Testing & Quality Assurance

This project includes comprehensive testing and quality assurance tools.

#### Running Tests:

```bash
cd agents-goose
./scripts/test.sh                    # Run all tests
./scripts/test.sh --unit            # Run only unit tests
./scripts/test.sh --integration     # Run only integration tests
./scripts/test.sh --performance     # Run only performance tests

# Direct pytest commands:
python -m pytest tests/              # Run all tests
python -m pytest tests/ -k "test_name"  # Run specific test
python -m pytest tests/ --pdb        # Debug failing tests
```

**Current Status:** 66/80 tests pass. Test infrastructure is in place with comprehensive edge case coverage. Some tests need refinement but demonstrate proper testing patterns.

#### Test Structure:

- **`tests/test_*.py`** - Comprehensive test suites for each module
- **Parallel execution** - Uses all CPU cores for faster test runs
- **Coverage reporting** - 80% minimum coverage requirement
- **Edge case testing** - Tests for boundary conditions and error scenarios

#### Test Categories:

- **Unit Tests** - Individual function/component testing
- **Integration Tests** - Multi-component interaction testing
- **Performance Tests** - Load and concurrency testing
- **Edge Case Tests** - Boundary condition and error handling

#### Pre-commit Hooks:

The project includes automated quality checks that run before each commit:

```bash
# The pre-commit hook automatically:
# 1. Runs auto-fix for linting issues (isort + black)
# 2. Executes the full test suite
# 3. Prevents commits if quality checks fail
# 4. Auto-stages fixed files

# To bypass checks for urgent commits:
git commit --no-verify -m "Urgent fix"
```

#### Test Coverage:

The test suite provides:
- **Comprehensive edge case testing** - Boundary conditions, error scenarios, concurrency
- **Parallel execution** - Uses all CPU cores for faster test runs
- **Extensive mocking** - Tests external API interactions safely
- **Performance testing** - Load and timing validations
- **Integration coverage** - Tests for all major modules (goose_server, dagster_tool, github_pr_reviewer)

### Dagster Pipeline Operations

Goose can interact with Dagster pipelines using the built-in `dagster_tool.py` module. This allows for pipeline execution, backfills, and status monitoring.

#### Available Operations:

**Pipeline Management:**
```python
from dagster_tool import run_dagster_pipeline, run_dagster_backfill, check_dagster_pipeline_status

# Launch a pipeline
result = run_dagster_pipeline("etl_pipeline", "__repository__")

# Launch with custom config
run_config = {"solids": {"my_solid": {"config": {"param": "value"}}}}
result = run_dagster_pipeline("etl_pipeline", "__repository__", run_config)

# Run a backfill
result = run_dagster_backfill("daily_partition_set", ["2023-01-01", "2023-12-31"])

# Check pipeline status
result = check_dagster_pipeline_status("run-123")

# List pipelines
result = list_dagster_pipelines("default")
```

**Example Goose Tasks:**
```
"Launch the ETL pipeline in production mode:
1. Execute: run_dagster_pipeline('etl_pipeline', '__repository__')
2. Monitor the execution status
3. Report any errors or confirm success"

"Run a backfill for the data pipeline from January to March 2024:
1. Execute: run_dagster_backfill('daily_partition_set', ['2024-01-01', '2024-02-01', '2024-03-01'])
2. Check that the backfill started successfully"
```

### Data Catalog Tools

Goose can interact with AWS Athena, AWS Glue, Trino, and DataHub using built-in tool modules. This allows Goose to explore database schemas and query data dictionary information directly.

#### Available Operations:

**AWS Glue (`glue_tool.py`):**
```python
from glue_tool import list_glue_databases

# List all databases
glue_dbs = list_glue_databases()
```

**AWS Athena (`athena_tool.py`):**
```python
from athena_tool import list_athena_databases, get_athena_create_statement

# List all databases
athena_dbs = list_athena_databases()

# Get table schema
schema = get_athena_create_statement("my_database", "my_table", s3_output="s3://my-athena-results/")
```

**Trino (`trino_tool.py`):**
```python
from trino_tool import list_trino_databases, get_trino_create_statement

# List all Trino databases (catalogs & schemas)
trino_dbs = list_trino_databases()

# Get table schema
schema = get_trino_create_statement("my_catalog", "my_schema", "my_table")
```

**DataHub (`datahub_tool.py`):**
```python
from datahub_tool import search_datahub_dataset, get_datahub_table_description, get_datahub_column_description

# Search for a dataset by name
results = search_datahub_dataset("users_table")
urn = results[0]["urn"]

# Get table and column descriptions
table_desc = get_datahub_table_description(urn)
col_desc = get_datahub_column_description(urn, "user_id")
```

**Example Goose Tasks:**
```
"Can you look up the schema for the 'transactions' table in Trino? Use list_trino_databases() and get_trino_create_statement() to find it."

"Search DataHub for 'customer_profiles' and tell me the description of the 'lifetime_value' column."
```

#### Requirements:

- **AWS:** Requires `boto3` to be installed and standard AWS credentials to be configured. The Athena queries require `ATHENA_S3_OUTPUT` environment variable to be set.
- **Trino:** By default, connects to `http://localhost:8080`. Override with `TRINO_HOST` and `TRINO_USER` environment variables.
- **DataHub:** By default, connects to `http://localhost:8080/api/graphql`. Override with `DATAHUB_URL` and `DATAHUB_TOKEN`.

#### Tool Functions:

- **`run_dagster_pipeline(pipeline_name, repository_name="__repository__", run_config=None)`**
  - Launches a new pipeline run via GraphQL API

- **`run_dagster_backfill(partition_set_name, partition_names, from_failure=False)`**
  - Executes a backfill for specified partitions via GraphQL

- **`check_dagster_pipeline_status(run_id)`**
  - Gets the status of a specific pipeline run

- **`list_dagster_pipelines(repository_name="default")`**
  - Lists all available pipelines in a repository

- **`list_dagster_runs(pipeline_name=None, limit=10)`**
  - Lists recent pipeline runs with optional filtering

#### Requirements:

- **Dagster Webserver must be running** (provides GraphQL API at http://localhost:3000/graphql)
- **Network access** to Dagster GraphQL endpoint
- **Proper repository and pipeline names** as configured in Dagster
- **Optional**: Configure `DAGSTER_GRAPHQL_URL` environment variable for custom endpoint

#### Integration with Goose:

The `dagster_tool.py` is automatically available in Goose's execution environment. Simply reference the functions in your task descriptions and Goose will execute them using the Dagster GraphQL API.

### Code Quality & Linting

This project includes comprehensive linting tools for Python, YAML, and shell scripts to maintain code quality.

#### Linting Tools Included:

- **Python**: `black` (formatting), `isort` (import sorting), `flake8` (style), `mypy` (type checking)
- **YAML**: `yamllint` (syntax and formatting)
- **Shell**: `shellcheck` (syntax and best practices)

#### Run Linting:

```bash
cd agents-goose
./scripts/lint.sh
```

This will run all linters and report any issues. The script will exit with code 0 if all checks pass, or code 1 if any issues are found.

#### Auto-fix Issues:

```bash
# Auto-fix formatting and import issues
./scripts/lint.sh --fix

# Or fix manually:
python -m isort src/ scripts/                    # Fix import sorting
python -m black src/ scripts/                    # Fix code formatting

# Check remaining issues
python -m flake8 src/ scripts/
```

#### Pre-commit Hooks:

The project includes a pre-commit hook that automatically runs linting before each commit:

```bash
# The hook will:
# 1. Run auto-fix (isort + black)
# 2. Run all linting checks
# 3. Auto-stage any fixed files
# 4. Prevent commit if issues remain

# To install the hook manually (usually automatic):
chmod +x .git/hooks/pre-commit
```

**Benefits:**
- ✅ **Automatic quality checks** - No bad code gets committed
- ✅ **Auto-fix integration** - Formatting issues fixed automatically
- ✅ **Team consistency** - Everyone follows the same standards
- ✅ **Early feedback** - Catch issues before they reach CI/CD

#### Configuration Files:

- **`pyproject.toml`** - Python linting configuration (black, isort, flake8, mypy)
- **`.yamllint.yaml`** - YAML linting configuration
- **`.shellcheckrc`** - Shell script linting configuration

#### CI/CD Integration:

The linting script can be integrated into CI/CD pipelines:

```yaml
# In GitHub Actions or similar
- name: Run Linting
  run: ./scripts/lint.sh
```

### Option 2: Manual startup

## Kubernetes Deployment

Deploy the entire Goose ecosystem to Kubernetes with separate pods for each service.

### Prerequisites

- Kubernetes cluster (local kind cluster as mentioned in @pulumi-k8s-kind)
- `kubectl` configured to access your cluster
- Docker registry access (for custom images)

### Quick Deploy

```bash
cd agents-goose

# 1. First, build the docker image for the Python apps and load it to your kind cluster
#    (If you are using a remote cluster, you would push the image to a registry)
docker build -t goose-app:latest .
kind load docker-image goose-app:latest --name local

# 2. Deploy all services to Kubernetes
./scripts/deploy-k8s.sh

# Start all services
./scripts/start-k8s.sh

# Monitor services
./scripts/monitor-k8s.sh
```

### Kubernetes Architecture

The deployment creates the following pods in the `goose-system` namespace:

- **`litellm`** - LLM proxy service (port 4321)
- **`goose-server`** - Main Goose task server (port 8765)
- **`slack-server`** - Slack slash commands handler (port 3000)
- **`slack-events`** - Slack @mentions handler (port 3001)
- **`github-pr-reviewer`** - GitHub PR review webhook handler (port 4000)

### Service Management

```bash
# Start all services
./scripts/start-k8s.sh

# Stop all services
./scripts/stop-k8s.sh

# Monitor all services
./scripts/monitor-k8s.sh

# View logs for a specific service
kubectl logs -f deployment/goose-server -n goose-system

# Scale individual services
kubectl scale deployment goose-server --replicas=2 -n goose-system
```

### Configuration

**Update secrets with your actual API keys:**
```bash
kubectl edit secret goose-secrets -n goose-system
```

**Update configuration:**
```bash
kubectl edit configmap goose-config -n goose-system
```

### External Access

Services are exposed via LoadBalancer services. Get external IPs:
```bash
kubectl get services -n goose-system
```

Use these IPs to configure:
- **Slack Apps** - Webhook URLs for slash commands and events
- **GitHub Webhooks** - PR review webhook URL
- **External Access** - Direct API access if needed

### Troubleshooting

```bash
# Check pod status
kubectl get pods -n goose-system

# Check service health
kubectl describe service <service-name> -n goose-system

# View detailed pod logs
kubectl describe pod <pod-name> -n goose-system

# Restart a failing deployment
kubectl rollout restart deployment/<deployment-name> -n goose-system
```

## Run test client

```bash
cd agents-goose
source .venv/bin/activate
python src/goose_task.py --task "Write a hello world program in Python" --wait
```

You can optionally specify a different model (defaults to `bedrock-claude-opus-4-6`):

```bash
python src/goose_task.py --task "Write a hello world program" --model bedrock-claude-opus-4-6 --wait
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
