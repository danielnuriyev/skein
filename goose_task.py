#!/usr/bin/env python3
"""
CLI script to submit Goose tasks to the local task server.

This script allows submitting tasks either from command-line text or from a file.
It can optionally wait for task completion and display final results.

Usage:
    python goose_task.py --task "Write a hello world program"
    python goose_task.py --task-file tasks/hello.txt --wait
"""

import argparse
from pathlib import Path

from goose_client import GooseTaskClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a Goose task from CLI text or a task file, optionally waiting for completion."
    )
    parser.add_argument(
        "--task",
        help="Task text to submit.",
    )
    parser.add_argument(
        "--task-file",
        help="Path to a file containing the task text.",
    )
    parser.add_argument(
        "--model",
        default="bedrock-nova-lite",
        help="Model to use for the task (default: bedrock-nova-lite).",
    )
    parser.add_argument(
        "--server-url",
        default="http://127.0.0.1:8765",
        help="Task server base URL (default: http://127.0.0.1:8765).",
    )
    parser.add_argument(
        "--working-directory",
        default=None,
        help="Optional working directory for Goose task execution.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the task to complete and show final status.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Seconds between status checks when waiting (default: 2.0).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Maximum seconds to wait for task completion (default: 600.0).",
    )

    args = parser.parse_args()
    if bool(args.task) == bool(args.task_file):
        parser.error("Provide exactly one of --task or --task-file.")
    return args


def read_task_from_file(path_value: str) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Task file is empty: {path}")
    return content


def main() -> None:
    args = parse_args()

    if args.task:
        task_text = args.task.strip()
        if not task_text:
            raise ValueError("--task cannot be empty.")
    else:
        task_text = read_task_from_file(args.task_file)

    client = GooseTaskClient(args.server_url)
    response = client.submit_task(
        task_text,
        working_directory=args.working_directory,
        model=args.model,
    )

    print(f"task_id={response['task_id']}")
    print(f"status={response['status']}")

    if args.wait:
        print("Waiting for task to complete...")
        final_status = client.wait_for_done(
            response['task_id'],
            poll_interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout
        )
        print(f"final_status={final_status['status']}")
        if final_status.get('error'):
            print(f"error: {final_status['error']}")
        if final_status.get('stdout'):
            print(f"stdout: {final_status['stdout']}")
        if final_status.get('stderr'):
            print(f"stderr: {final_status['stderr']}")
        print("done")


if __name__ == "__main__":
    main()
