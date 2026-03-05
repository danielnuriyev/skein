#!/usr/bin/env python3
"""
Slack middleware server for Goose task management.

This server acts as a bridge between Slack and the Goose task server.
It receives Slack commands, submits tasks to src/goose_server.py, and sends
results back to Slack channels.

Slack Integration Setup:
1. Create a Slack App with Slash Commands
2. Set the Request URL to: https://your-domain.ngrok.io/slack/command
3. Configure the slash command (e.g., /goose)
4. Use ngrok or similar to expose this server publicly

API Endpoints:
- POST /slack/command: Handle Slack slash commands

Environment Variables:
- SLACK_SIGNING_SECRET: For request verification (optional but recommended)
- GOOSE_SERVER_URL: URL of src/goose_server.py (default: http://localhost:8765)
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bottle import Bottle, request, response, run

app = Bottle()

# Configuration
GOOSE_SERVER_URL = os.getenv("GOOSE_SERVER_URL", "http://localhost:8765")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")


def submit_goose_task(task_text: str, model: str = "bedrock-claude-opus-4-6") -> str:
    """Submit a task to the Goose server and return the task_id."""
    payload = {"task": task_text, "model": model, "working_directory": str(Path.cwd())}

    req = Request(
        f"{GOOSE_SERVER_URL}/tasks",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["task_id"]
    except Exception as e:
        raise Exception(f"Failed to submit task to Goose server: {str(e)}")


def get_task_status(task_id: str) -> dict:
    """Get the current status of a Goose task."""
    req = Request(f"{GOOSE_SERVER_URL}/tasks/{task_id}")

    try:
        with urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise Exception(f"Failed to get task status: {str(e)}")


def wait_for_task_completion(task_id: str, timeout_seconds: int = 600) -> dict:
    """Poll for task completion and return final status."""
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        try:
            status = get_task_status(task_id)
            if status["status"] in ["completed", "failed"]:
                return status
        except Exception as e:
            # If we can't get status, keep trying
            pass

        time.sleep(2)  # Poll every 2 seconds

    # Timeout reached
    return {"status": "timeout", "error": f"Task timed out after {timeout_seconds} seconds"}


def send_slack_response(response_url: str, message: str, is_error: bool = False) -> None:
    """Send a response back to Slack using the response_url."""
    payload = {
        "text": message,
        "response_type": "in_channel",  # Makes the response visible to the whole channel
    }

    if is_error:
        payload["text"] = f"❌ Error: {message}"

    req = Request(
        response_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req) as response:
            pass  # Success
    except Exception as e:
        print(f"Failed to send Slack response: {str(e)}")


def format_task_output(task_result: dict) -> str:
    """Format the task result for Slack display."""
    if task_result["status"] == "completed":
        output = task_result.get("stdout", "").strip()
        if output:
            # Truncate very long outputs for Slack
            if len(output) > 3000:
                output = output[:3000] + "...\n\n(Output truncated)"
            return f"✅ Task completed successfully!\n\n{output}"
        else:
            return "✅ Task completed successfully! (no output)"

    elif task_result["status"] == "failed":
        error = task_result.get("error", "Unknown error")
        stderr = task_result.get("stderr", "").strip()
        exit_code = task_result.get("exit_code", "unknown")

        message = f"❌ Task failed (exit code: {exit_code})\n\nError: {error}"
        if stderr:
            message += f"\n\nStderr:\n{stderr[:2000]}"  # Truncate stderr
        return message

    elif task_result["status"] == "timeout":
        return "⏰ Task timed out. The operation took too long to complete."

    else:
        return f"❓ Unknown status: {task_result.get('status', 'unknown')}"


@app.route("/slack/command", method="POST")
def handle_slack_command():
    """Handle incoming Slack slash commands."""
    try:
        # Get the raw form data (Slack sends URL-encoded data)
        text = request.forms.get("text", "").strip()
        response_url = request.forms.get("response_url")
        user_name = request.forms.get("user_name", "unknown")

        # Validate required fields
        if not text:
            response.content_type = "application/json"
            return {
                "text": "❌ Usage: /goose <your task description>",
                "response_type": "ephemeral",
            }

        if not response_url:
            response.content_type = "application/json"
            return {"text": "❌ Missing response_url from Slack", "response_type": "ephemeral"}

        # Immediately acknowledge Slack (required within 3 seconds)
        # We'll send the actual response later via response_url
        response_payload = {
            "text": f"🤖 Processing your request, {user_name}...",
            "response_type": "ephemeral",  # Only visible to the user who issued the command
        }

        # Start the async task processing in a background thread
        import threading

        def process_task():
            try:
                # Submit task to Goose server
                task_id = submit_goose_task(text)
                print(f"Submitted task {task_id} for user {user_name}: {text[:100]}...")

                # Wait for completion
                result = wait_for_task_completion(task_id)

                # Format and send response to Slack
                slack_message = format_task_output(result)
                send_slack_response(response_url, slack_message, result["status"] == "failed")

            except Exception as e:
                error_msg = f"Failed to process task: {str(e)}"
                print(f"Error processing task for {user_name}: {error_msg}")
                send_slack_response(response_url, error_msg, is_error=True)

        # Start background thread
        thread = threading.Thread(target=process_task, daemon=True)
        thread.start()

        # Return immediate acknowledgment to Slack
        response.content_type = "application/json"
        return response_payload

    except Exception as e:
        print(f"Error handling Slack command: {str(e)}")
        response.content_type = "application/json"
        return {"text": f"❌ Internal server error: {str(e)}", "response_type": "ephemeral"}


@app.route("/health", method="GET")
def health_check():
    """Health check endpoint."""
    response.content_type = "application/json"
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    print(f"Slack middleware server starting on port {port}")
    print(f"Goose server URL: {GOOSE_SERVER_URL}")
    print("Configure your Slack app to send slash commands to: /slack/command")

    run(app, host="0.0.0.0", port=port, debug=False)
