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
import subprocess
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


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_task(task_id: str) -> None:
    with TASKS_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            return
        task["status"] = "running"
        task["started_at"] = utc_now()
        task["updated_at"] = utc_now()
        task["error"] = None

    cmd = ["goose", "run", "--text", task["task"]]
    if task.get("model"):
        cmd.extend(["--model", task["model"]])
    cwd = task["working_directory"]

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        status = "completed" if result.returncode == 0 else "failed"
        error = None if result.returncode == 0 else "goose returned non-zero exit code"
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
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
