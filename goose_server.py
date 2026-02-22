#!/usr/bin/env python3
"""
Local HTTP server for Goose task management.

This server provides a REST API for submitting Goose tasks and monitoring their status.
Tasks are executed asynchronously using the 'goose run --text' command, with status tracking
and output collection.

API Endpoints:
- POST /tasks: Submit a new task with optional working directory
- GET /tasks: List all tasks
- GET /tasks/<task_id>: Get specific task status and results

Task states: queued -> running -> completed/failed
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse


TERMINAL_STATUSES = {"completed", "failed"}
TASKS: Dict[str, dict] = {}
TASKS_LOCK = threading.Lock()
DEFAULT_MAX_TURNS = 40
DEFAULT_MAX_TOOL_REPETITIONS = 3
DEFAULT_TIMEOUT_SECONDS = 300


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_task_prompt(task_text: str) -> str:
    guardrails = (
        "Important execution requirements:\n"
        "- Apply changes directly to files in the working directory.\n"
        "- Do not delegate, do not spawn background subtasks, and do not use app generators.\n"
        "- Use direct file edit and shell tools only.\n"
        "- After editing, verify by reading the target file(s).\n"
    )
    return f"{task_text.strip()}\n\n{guardrails}"


def run_task(task_id: str) -> None:
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            return
        task["status"] = "running"
        task["started_at"] = utc_now()
        task["updated_at"] = utc_now()
        task["error"] = None

    # Create a temporary config directory for isolated Goose configuration
    script_dir = Path(__file__).parent
    project_config = script_dir / "goose_config.yaml"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_config_dir = Path(tmpdir)
        goose_subdir = tmp_config_dir / "goose"
        goose_subdir.mkdir(parents=True)

        if project_config.exists():
            shutil.copy(project_config, goose_subdir / "config.yaml")

        # Set environment to use local config directory
        env = os.environ.copy()
        env["XDG_CONFIG_HOME"] = str(tmp_config_dir)

        cmd = [
            "goose",
            "run",
            "--text",
            build_task_prompt(task["task"]),
            "--max-turns",
            str(task.get("max_turns", DEFAULT_MAX_TURNS)),
            "--max-tool-repetitions",
            str(task.get("max_tool_repetitions", DEFAULT_MAX_TOOL_REPETITIONS)),
        ]
        if task.get("model"):
            cmd.extend(["--model", task["model"]])
        cwd = task["working_directory"]
        timeout_seconds = int(task.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
                env=env,
            )
            status = "completed" if result.returncode == 0 else "failed"
            error = None if result.returncode == 0 else "goose returned non-zero exit code"
            stdout = result.stdout
            stderr = result.stderr
            exit_code = result.returncode
        except subprocess.TimeoutExpired as exc:
            status = "failed"
            error = f"goose timed out after {timeout_seconds} seconds"
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            exit_code = 124
        except Exception as exc:  # pragma: no cover
            status = "failed"
            error = str(exc)
            stdout = ""
            stderr = ""
            exit_code = -1

    with TASKS_LOCK:
            if task_id not in TASKS:
                return
            TASKS[task_id]["status"] = status
            TASKS[task_id]["completed_at"] = utc_now()
            TASKS[task_id]["updated_at"] = utc_now()
            TASKS[task_id]["exit_code"] = exit_code
            TASKS[task_id]["stdout"] = stdout
            TASKS[task_id]["stderr"] = stderr
            TASKS[task_id]["error"] = error


class TaskHandler(BaseHTTPRequestHandler):
    server_version = "GooseTaskServer/1.0"

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return

        if path == "/tasks":
            with TASKS_LOCK:
                tasks = list(TASKS.values())
            self._send_json(200, {"tasks": tasks})
            return

        if path.startswith("/tasks/"):
            task_id = path.split("/", 2)[2]
            with TASKS_LOCK:
                task = TASKS.get(task_id)
            if task is None:
                self._send_json(404, {"error": "task not found"})
                return
            self._send_json(200, task)
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path != "/tasks":
            self._send_json(404, {"error": "not found"})
            return

        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid json"})
            return

        task_text = payload.get("task")
        if not isinstance(task_text, str) or not task_text.strip():
            self._send_json(400, {"error": "field 'task' is required"})
            return

        requested_cwd = payload.get("working_directory")
        if requested_cwd is None:
            working_directory = str(Path.cwd())
        elif isinstance(requested_cwd, str) and requested_cwd.strip():
            working_directory = requested_cwd
        else:
            self._send_json(400, {"error": "working_directory must be a non-empty string"})
            return

        if not Path(working_directory).exists():
            self._send_json(400, {"error": "working_directory does not exist"})
            return

        task_id = str(uuid.uuid4())
        record = {
            "task_id": task_id,
            "task": task_text,
            "model": payload.get("model"),
            "max_turns": payload.get("max_turns", DEFAULT_MAX_TURNS),
            "max_tool_repetitions": payload.get("max_tool_repetitions", DEFAULT_MAX_TOOL_REPETITIONS),
            "timeout_seconds": payload.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
            "status": "queued",
            "working_directory": working_directory,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "started_at": None,
            "completed_at": None,
            "exit_code": None,
            "stdout": None,
            "stderr": None,
            "error": None,
        }

        with TASKS_LOCK:
            TASKS[task_id] = record

        worker = threading.Thread(target=run_task, args=(task_id,), daemon=True)
        worker.start()

        self._send_json(202, {"task_id": task_id, "status": "queued"})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        # Keep output quiet for readability.
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Goose task server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), TaskHandler)
    print(f"Goose task server listening on http://{args.host}:{args.port}")
    print("POST /tasks with JSON {\"task\": \"...\"} to submit work.")
    print("GET /tasks/<task_id> to read status.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
