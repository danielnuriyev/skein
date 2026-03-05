#!/usr/bin/env python3
"""
GitHub PR Reviewer for Goose task management.

This server integrates with GitHub webhooks to automatically review pull requests
using Goose AI. When a PR is opened or updated, it:

1. Receives the webhook from GitHub
2. Fetches PR details (diff, files, description)
3. Submits review request to Goose
4. Posts the review back to GitHub

GitHub Webhook Setup:
1. Go to your repository Settings → Webhooks
2. Add webhook with URL: https://your-domain.ngrok.io/webhook
3. Content type: application/json
4. Events: Pull requests
5. Add webhook secret for verification

Environment Variables:
- GITHUB_WEBHOOK_SECRET: For webhook signature verification
- GITHUB_TOKEN: For posting reviews (optional, if needed)
- GOOSE_SERVER_URL: URL of goose_server.py (default: http://localhost:8765)
"""

import hashlib
import hmac
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen, urlretrieve

from bottle import Bottle, abort, request, response

app = Bottle()

# Configuration
GOOSE_SERVER_URL = os.getenv("GOOSE_SERVER_URL", "http://localhost:8765")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


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


def wait_for_task_completion(
    task_id: str, timeout_seconds: int = 1200
) -> dict:  # 20 minutes for PR reviews
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

        time.sleep(5)  # Poll every 5 seconds for PR reviews

    # Timeout reached
    return {"status": "timeout", "error": f"PR review timed out after {timeout_seconds} seconds"}


def verify_github_webhook() -> bool:
    """Verify that the request came from GitHub using webhook secret."""
    if not GITHUB_WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured

    signature = request.headers.get("X-Hub-Signature-256", "")
    body = request.body.read()

    if not signature:
        return False

    # Create expected signature
    expected_signature = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    expected_signature = f"sha256={expected_signature}"

    return hmac.compare_digest(expected_signature, signature)


def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Fetch the PR diff from GitHub API."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

    headers = {"Accept": "application/vnd.github.v3.diff"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = Request(url, headers=headers)

    try:
        with urlopen(req) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        raise Exception(f"Failed to fetch PR diff: {str(e)}")


def parse_line_comments(review_content: str) -> tuple[str, list[dict]]:
    """Parse AI review response to extract overall comment and line-specific comments.

    Returns:
        tuple: (overall_comment, line_comments_list)
        where line_comments_list contains dicts with 'path', 'line', 'body' keys
    """
    line_comments = []

    # Find all FILE: markers and their positions
    file_pattern = r"FILE:\s*([^\s:]+):(\d+)"
    file_matches = list(re.finditer(file_pattern, review_content, re.IGNORECASE))

    if not file_matches:
        # No line-specific comments found, return everything as overall
        return review_content.strip(), []

    # Extract overall content (everything before first FILE: marker)
    first_match = file_matches[0]
    overall_comment = review_content[: first_match.start()].strip()

    # Process each FILE: section
    for i, match in enumerate(file_matches):
        file_path = match.group(1)
        line_number = int(match.group(2))

        # Determine end position (next FILE: marker or next section header)
        start_pos = match.end()

        # Look for end markers: next FILE:, or section headers like ##
        remaining_content = review_content[start_pos:]
        end_patterns = [
            (r"FILE:\s*[^\s:]+\:\d+", re.IGNORECASE),  # Next FILE: marker
            (r"^##\s+", re.MULTILINE),  # Section headers
            (r"^\*\*.*\*\*$", re.MULTILINE),  # Bold section headers
        ]

        end_pos = len(review_content)  # Default to end of content
        for pattern, flags in end_patterns:
            next_match = re.search(pattern, remaining_content, flags)
            if next_match:
                candidate_end = start_pos + next_match.start()
                if candidate_end < end_pos:
                    end_pos = candidate_end

        # Extract comment content for this file/line
        comment_content = review_content[start_pos:end_pos].strip()

        # Clean up the comment (remove leading/trailing whitespace and empty lines)
        comment_lines = [line for line in comment_content.split("\n") if line.strip()]
        comment_content = "\n".join(comment_lines).strip()

        if comment_content:
            line_comments.append({"path": file_path, "line": line_number, "body": comment_content})

    return overall_comment, line_comments


def post_github_review(
    repo_full_name: str, pr_number: int, review_body: str, event: str = "COMMENT"
):
    """Post a comprehensive review to GitHub PR with overall comment and line-specific comments."""

    if not GITHUB_TOKEN:
        print(f"Would post review to {repo_full_name}#{pr_number}: {review_body[:100]}...")
        return

    # Parse the review content to separate overall and line-specific comments
    overall_comment, line_comments = parse_line_comments(review_body)

    # Format overall comment for display
    if overall_comment:
        formatted_overall = f"""## 🤖 Goose AI Code Review

{overall_comment}

---
*This review was generated automatically by Goose AI. Please consider the suggestions and implement improvements as appropriate.*"""
    else:
        formatted_overall = """## 🤖 Goose AI Code Review

*This review was generated automatically by Goose AI.*"""

    # Prepare the review payload for Pull Request Reviews API
    payload = {
        "body": formatted_overall,
        "event": "COMMENT",  # Can be "COMMENT", "APPROVE", "REQUEST_CHANGES"
        "comments": [],
    }

    # Add line-specific comments if any were parsed
    for comment in line_comments:
        # Convert line number to position (approximate, GitHub uses positions in diff)
        # For simplicity, we'll use the line number as position
        # In a more sophisticated implementation, you'd need to map line numbers to diff positions
        payload["comments"].append(
            {
                "path": comment["path"],
                "position": comment["line"],  # This is an approximation
                "body": f"🤖 **Goose AI Comment:**\n\n{comment['body']}",
            }
        )

    # Use Pull Request Reviews API instead of Issues API
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"

    headers = {"Content-Type": "application/json", "Authorization": f"token {GITHUB_TOKEN}"}

    req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

    try:
        with urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"Posted comprehensive review to {repo_full_name}#{pr_number}")
            if line_comments:
                print(f"Included {len(line_comments)} line-specific comments")
            return result
    except Exception as e:
        print(f"Failed to post GitHub review: {str(e)}")
        # Fallback to simple comment if review API fails
        fallback_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
        fallback_payload = {"body": formatted_overall}

        try:
            fallback_req = Request(
                fallback_url,
                data=json.dumps(fallback_payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(fallback_req) as response:
                print(f"Fell back to simple comment for {repo_full_name}#{pr_number}")
        except Exception as fallback_error:
            print(f"Fallback comment also failed: {str(fallback_error)}")


def format_pr_review_request(event_data: dict) -> str:
    """Format PR information into a review request for Goose."""
    pr = event_data.get("pull_request", {})
    repo = event_data.get("repository", {})

    pr_number = pr.get("number")
    pr_title = pr.get("title", "")
    pr_body = pr.get("body", "")
    repo_name = repo.get("full_name", "")
    branch = pr.get("head", {}).get("ref", "")

    # Note on architecture choice: Diff vs Clone
    # Currently, this uses a lightweight "ChatGPT-style" approach: fetching the PR diff
    # and pasting it directly into the prompt. This is fast and stateless, but limits
    # Goose's context to only the changed lines and truncates large PRs.
    #
    # To unlock Goose's full potential as an autonomous software engineer (allowing it
    # to read surrounding code, trace function calls across files, or run linters/tests),
    # this could be upgraded to clone the repository into a temporary directory,
    # checkout the PR branch, and set that as Goose's working_directory.

    # Try to fetch the diff
    diff_content = ""
    try:
        diff_content = fetch_pr_diff(repo_name, pr_number)
    except Exception:
        print("Could not fetch diff - using placeholder")
        diff_content = "Diff not available"

    # Read review guidelines from external file
    guidelines_content = ""
    try:
        script_dir = Path(__file__).parent.parent
        guidelines_file = script_dir / "prompts" / "github_pr_reviewer.md"
        if guidelines_file.exists():
            with open(guidelines_file, "r", encoding="utf-8") as f:
                guidelines_content = f.read().strip()
        else:
            print(f"Warning: Review guidelines file not found at {guidelines_file}")
            guidelines_content = "**Review Guidelines:**\n- Focus on code quality, bugs, security issues, and best practices\n- Check for proper error handling and edge cases\n- Review code style and documentation\n- Suggest improvements and optimizations\n- Be constructive and helpful\n\nPlease provide a comprehensive code review with specific comments, suggestions, and an overall assessment."
    except Exception as e:
        print(f"Error reading review guidelines: {e}")
        guidelines_content = "**Review Guidelines:**\n- Focus on code quality, bugs, security issues, and best practices\n- Check for proper error handling and edge cases\n- Review code style and documentation\n- Suggest improvements and optimizations\n- Be constructive and helpful\n\nPlease provide a comprehensive code review with specific comments, suggestions, and an overall assessment."

    # Format the review request
    review_prompt = f"""Please review this GitHub pull request:

**Repository:** {repo_name}
**PR #{pr_number}:** {pr_title}
**Branch:** {branch}

**Description:**
{pr_body or "No description provided"}

**Changes (diff):**
```diff
{diff_content[:50000]}  # Limit diff size
```

{guidelines_content}"""

    return review_prompt


def format_review_response(task_result: dict, pr_data: dict) -> str:
    """Extract the raw Goose review response for processing."""
    if task_result["status"] == "completed":
        review_content = task_result.get("stdout", "").strip()
        return review_content if review_content else "🤖 Goose AI Review: No output generated"

    elif task_result["status"] == "failed":
        error = task_result.get("error", "Unknown error")
        return f"❌ Review failed: {error}"

    elif task_result["status"] == "timeout":
        return "⏰ Review timed out. The analysis took too long to complete."

    else:
        return f"❓ Unknown review status: {task_result.get('status', 'unknown')}"


@app.route("/webhook", method="POST")
def handle_github_webhook():
    """Handle incoming GitHub webhooks."""
    try:
        # Verify webhook signature
        if not verify_github_webhook():
            abort(401, "Invalid webhook signature")

        # Parse the webhook payload
        event_data = request.json
        event_type = request.headers.get("X-GitHub-Event", "")

        # Only process pull request events
        if event_type != "pull_request":
            response.status = 200
            return {"ok": True, "ignored": f"Event type: {event_type}"}

        # Check the action (opened, synchronize, etc.)
        action = event_data.get("action")
        if action not in ["opened", "synchronize", "reopened"]:
            response.status = 200
            return {"ok": True, "ignored": f"PR action: {action}"}

        pr = event_data.get("pull_request", {})
        pr_number = pr.get("number")
        repo = event_data.get("repository", {})
        repo_name = repo.get("full_name", "")

        print(f"Processing PR review: {repo_name}#{pr_number} ({action})")

        # Format the review request
        review_request = format_pr_review_request(event_data)

        # Submit to Goose for review
        try:
            task_id = submit_goose_task(review_request)
            print(f"Submitted PR review task {task_id}")

            # Wait for completion (this may take time for large PRs)
            result = wait_for_task_completion(task_id)

            # Format and post the review
            review_comment = format_review_response(result, event_data)
            post_github_review(repo_name, pr_number, review_comment)

            response.status = 200
            return {"ok": True, "task_id": task_id}

        except Exception as e:
            error_msg = f"Failed to process PR review: {str(e)}"
            print(error_msg)

            # Still try to post an error comment
            error_comment = f"❌ Failed to generate AI review: {str(e)}"
            post_github_review(repo_name, pr_number, error_comment)

            response.status = 500
            return {"error": error_msg}

    except Exception as e:
        print(f"Error handling GitHub webhook: {str(e)}")
        response.status = 500
        return {"error": "Internal server error"}


@app.route("/health", method="GET")
def health_check():
    """Health check endpoint."""
    response.content_type = "application/json"
    return {"status": "ok", "service": "github-pr-reviewer"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "4000"))  # Different default port
    print(f"GitHub PR Reviewer starting on port {port}")
    print(f"Goose server URL: {GOOSE_SERVER_URL}")
    print("Configure GitHub webhook to: /webhook")
    if not GITHUB_WEBHOOK_SECRET:
        print("⚠️  WARNING: GITHUB_WEBHOOK_SECRET not set - webhook verification disabled")
    if not GITHUB_TOKEN:
        print("⚠️  WARNING: GITHUB_TOKEN not set - will not post reviews to GitHub")

    from bottle import run

    run(app, host="0.0.0.0", port=port, debug=False)
