#!/usr/bin/env python3
"""
Python client for the Goose task server API.

Provides a simple interface to submit tasks, check status, and wait for completion.
Communicates with the local Goose task server via HTTP requests.

Key methods:
- submit_task(): Submit a new task for execution
- get_task_status(): Check status of a specific task
- wait_for_done(): Poll until task reaches terminal state
"""

import json
import time
from typing import Optional
from urllib import request


class GooseTaskClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8765") -> None:
        self.base_url = base_url.rstrip("/")

    def submit_task(
        self,
        task: str,
        working_directory: Optional[str] = None,
        model: Optional[str] = None,
        max_turns: Optional[int] = None,
        max_tool_repetitions: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> dict:
        payload = {"task": task}
        if working_directory is not None:
            payload["working_directory"] = working_directory
        if model is not None:
            payload["model"] = model
        if max_turns is not None:
            payload["max_turns"] = max_turns
        if max_tool_repetitions is not None:
            payload["max_tool_repetitions"] = max_tool_repetitions
        if timeout_seconds is not None:
            payload["timeout_seconds"] = timeout_seconds
        return self._request_json("POST", "/tasks", payload)

    def get_task_status(self, task_id: str) -> dict:
        return self._request_json("GET", f"/tasks/{task_id}")

    def wait_for_done(
        self,
        task_id: str,
        poll_interval_seconds: float = 2.0,
        timeout_seconds: float = 600.0,
    ) -> dict:
        deadline = time.time() + timeout_seconds
        while True:
            status = self.get_task_status(task_id)
            if status.get("status") in {"completed", "failed"}:
                return status
            if time.time() > deadline:
                raise TimeoutError(f"timed out waiting for task {task_id}")
            time.sleep(poll_interval_seconds)

    def _request_json(self, method: str, path: str, payload: Optional[dict] = None) -> dict:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
