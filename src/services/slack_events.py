#!/usr/bin/env python3
"""
Slack Events Handler for Goose task management.

This server handles Slack Event Subscriptions, allowing the bot to react to:
- Messages mentioning the bot (@GooseBot)
- Messages in specific channels
- Direct messages
- Reactions and other events

Slack Event Setup:
1. In your Slack App, go to "Event Subscriptions"
2. Enable Events
3. Set Request URL to: https://your-domain.ngrok.io/events
4. Subscribe to bot events: app_mention, message.im
5. Subscribe to message events if needed

Environment Variables:
- SLACK_SIGNING_SECRET: Required for request verification
- SLACK_BOT_TOKEN: For sending responses (optional, if needed)
- GOOSE_SERVER_URL: URL of goose_server.py (default: http://localhost:8765)
"""

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from bottle import Bottle, abort, request, response

app = Bottle()

# Configuration
GOOSE_SERVER_URL = os.getenv("GOOSE_SERVER_URL", "http://localhost:8765")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")


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


def send_slack_message(channel: str, text: str) -> None:
    """Send a message to a Slack channel using the Web API."""
    if not SLACK_BOT_TOKEN:
        print(f"Would send to Slack channel {channel}: {text}")
        return

    payload = {"channel": channel, "text": text}

    req = Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        method="POST",
    )

    try:
        with urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            if not result.get("ok"):
                print(f"Failed to send Slack message: {result.get('error')}")
    except Exception as e:
        print(f"Failed to send Slack message: {str(e)}")


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


def verify_slack_request() -> bool:
    """Verify that the request came from Slack using signing secret."""
    if not SLACK_SIGNING_SECRET:
        return True  # Skip verification if no secret configured

    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not timestamp or not signature:
        return False

    # Check if timestamp is within 5 minutes
    current_time = int(time.time())
    request_time = int(timestamp)
    if abs(current_time - request_time) > 300:
        return False

    # Create the basestring
    body = request.body.read()
    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"

    # Create the expected signature
    expected_signature = hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"), basestring.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    expected_signature = f"v0={expected_signature}"

    return hmac.compare_digest(expected_signature, signature)


@app.route("/events", method="POST")
def handle_slack_event():
    """Handle incoming Slack events."""
    try:
        # Verify request signature
        if not verify_slack_request():
            abort(401, "Invalid request signature")

        # Parse the event payload
        event_data = request.json

        # Handle URL verification challenge
        if event_data.get("type") == "url_verification":
            response.content_type = "application/json"
            return {"challenge": event_data.get("challenge")}

        # Extract the actual event
        event = event_data.get("event", {})

        # Handle different event types
        event_type = event.get("type")

        if event_type == "app_mention":
            # Bot was mentioned (@GooseBot)
            return handle_app_mention(event)

        elif event_type == "message":
            # Regular message (could be DM or channel message)
            return handle_message(event)

        # Acknowledge other events
        response.status = 200
        return {"ok": True}

    except Exception as e:
        print(f"Error handling Slack event: {str(e)}")
        response.status = 500
        return {"error": "Internal server error"}


def handle_app_mention(event: dict):
    """Handle when the bot is mentioned (@GooseBot)."""
    try:
        text = event.get("text", "").strip()
        channel = event.get("channel")
        user = event.get("user")

        # Remove the bot mention from the text (e.g., "<@U123456> do something" -> "do something")
        # The mention format is <@USERID>
        import re

        text = re.sub(r"<@\w+>", "", text).strip()

        if not text:
            send_slack_message(
                channel,
                "Hey there! 👋 I'm GooseBot. Mention me with a task, like '@GooseBot write a hello world program'",
            )
            response.status = 200
            return {"ok": True}

        # Acknowledge the event immediately
        response.status = 200

        # Process the task asynchronously
        import threading

        def process_task():
            try:
                # Submit task to Goose server
                task_id = submit_goose_task(text)
                print(
                    f"Submitted task {task_id} from Slack mention by user {user}: {text[:100]}..."
                )

                # Send initial acknowledgment
                send_slack_message(channel, f"🤖 Processing your request...")

                # Wait for completion
                result = wait_for_task_completion(task_id)

                # Format and send response to Slack
                slack_message = format_task_output(result)
                send_slack_message(channel, slack_message)

            except Exception as e:
                error_msg = f"Failed to process task: {str(e)}"
                print(f"Error processing task from Slack mention: {error_msg}")
                send_slack_message(channel, f"❌ {error_msg}")

        # Start background thread
        thread = threading.Thread(target=process_task, daemon=True)
        thread.start()

        return {"ok": True}

    except Exception as e:
        print(f"Error handling app mention: {str(e)}")
        response.status = 500
        return {"error": "Internal server error"}


def handle_message(event: dict):
    """Handle regular messages (DMs, channel messages)."""
    # For now, just acknowledge the event
    # You could extend this to handle DMs or specific channel messages

    # Check if it's a DM (channel starts with 'D')
    channel = event.get("channel", "")
    if channel.startswith("D"):
        # This is a direct message
        text = event.get("text", "").strip()
        if text:
            # You could process DMs here if desired
            pass

    response.status = 200
    return {"ok": True}


@app.route("/health", method="GET")
def health_check():
    """Health check endpoint."""
    response.content_type = "application/json"
    return {"status": "ok", "service": "slack-events"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3001"))  # Different default port than slack_server.py
    print(f"Slack Events Handler starting on port {port}")
    print(f"Goose server URL: {GOOSE_SERVER_URL}")
    print("Configure your Slack app Event Subscriptions to: /events")
    if not SLACK_SIGNING_SECRET:
        print("⚠️  WARNING: SLACK_SIGNING_SECRET not set - request verification disabled")
    if not SLACK_BOT_TOKEN:
        print("ℹ️  SLACK_BOT_TOKEN not set - will only log messages (no sending)")

    from bottle import run

    run(app, host="0.0.0.0", port=port, debug=False)
