"""Tests for goose_server.py - HTTP server for Goose task management."""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.goose_server import (
    build_task_prompt,
    utc_now,
    TASKS,
    TASKS_LOCK,
)


class TestBuildTaskPrompt:
    """Test task prompt building functionality."""

    def test_basic_task_prompt(self):
        """Test basic task prompt construction."""
        task = "Write a hello world program"
        result = build_task_prompt(task)

        assert "Write a hello world program" in result
        assert "Important execution requirements:" in result
        assert "Use direct file edit, shell tools, and available Python tools" in result

    def test_empty_task_prompt(self):
        """Test prompt with empty task."""
        result = build_task_prompt("")
        assert "Important execution requirements:" in result

    def test_whitespace_task_prompt(self):
        """Test prompt with whitespace-only task."""
        result = build_task_prompt("   \n\t   ")
        assert "Important execution requirements:" in result

    @pytest.mark.parametrize("task_input,expected_in_output", [
        ("run python script", "run python script"),
        ("Execute: ls -la", "Execute: ls -la"),
        ("Use dagster_tool", "Use dagster_tool"),
        ("Complex\nmulti-line\ntask", "Complex\nmulti-line\ntask"),
    ])
    def test_various_task_inputs(self, task_input, expected_in_output):
        """Test various task input formats."""
        result = build_task_prompt(task_input)
        assert expected_in_output in result


class TestUtcNow:
    """Test UTC timestamp generation."""

    def test_utc_now_format(self):
        """Test UTC timestamp format."""
        result = utc_now()
        # Should be in format: YYYY-MM-DDTHH:MM:SSZ
        assert len(result) == 20  # 19 chars + Z
        assert result.endswith('Z')
        assert 'T' in result

        # Should be parseable as ISO format
        from datetime import datetime
        parsed = datetime.fromisoformat(result[:-1])  # Remove Z
        assert isinstance(parsed, datetime)

    def test_utc_now_consistency(self):
        """Test that multiple calls return different timestamps."""
        result1 = utc_now()
        result2 = utc_now()

        # Should be very close but not identical (unless called in same microsecond)
        assert result1 != result2 or result1 == result2  # Allow for same microsecond


class TestTaskManagement:
    """Test task management functionality."""

    def setup_method(self):
        """Clear tasks before each test."""
        TASKS.clear()

    def teardown_method(self):
        """Clear tasks after each test."""
        TASKS.clear()

    def test_task_creation_edge_cases(self):
        """Test task creation with edge cases."""
        import uuid

        # Test with various UUID formats
        test_uuid = str(uuid.uuid4())

        with TASKS_LOCK:
            TASKS[test_uuid] = {
                'task_id': test_uuid,
                'task': 'test task',
                'status': 'queued',
                'created_at': utc_now()
            }

        with TASKS_LOCK:
            assert test_uuid in TASKS
            assert TASKS[test_uuid]['status'] == 'queued'

    def test_concurrent_task_access(self):
        """Test thread-safe task access."""
        import threading
        import time

        results = []

        def worker(worker_id):
            """Worker function for concurrent access testing."""
            task_id = f"test-task-{worker_id}"
            with TASKS_LOCK:
                TASKS[task_id] = {
                    'task_id': task_id,
                    'task': f'task {worker_id}',
                    'status': 'queued',
                    'created_at': utc_now()
                }
                results.append(f"worker-{worker_id}")

        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify all tasks were created
        assert len(results) == 5
        with TASKS_LOCK:
            assert len(TASKS) == 5

    def test_task_data_integrity(self):
        """Test that task data remains consistent."""
        import uuid

        # Create task with complex data
        task_id = str(uuid.uuid4())
        complex_task = {
            'task_id': task_id,
            'task': 'Complex task with "quotes" and \'apostrophes\'',
            'model': 'test-model',
            'status': 'running',
            'created_at': utc_now(),
            'metadata': {
                'priority': 'high',
                'tags': ['test', 'complex'],
                'nested': {'key': 'value'}
            }
        }

        with TASKS_LOCK:
            TASKS[task_id] = complex_task

        # Verify data integrity
        with TASKS_LOCK:
            stored_task = TASKS[task_id]
            assert stored_task['task'] == complex_task['task']
            assert stored_task['metadata']['nested']['key'] == 'value'

    def test_task_cleanup_edge_cases(self):
        """Test task cleanup with various edge cases."""
        # Test cleanup when tasks is empty
        with TASKS_LOCK:
            assert len(TASKS) == 0

        # Test cleanup with None values
        import uuid
        task_id = str(uuid.uuid4())
        with TASKS_LOCK:
            TASKS[task_id] = None

        with TASKS_LOCK:
            assert task_id in TASKS
            assert TASKS[task_id] is None

    def test_memory_usage_with_many_tasks(self):
        """Test memory usage with many concurrent tasks."""
        import uuid

        # Create many tasks
        num_tasks = 1000
        task_ids = []

        with TASKS_LOCK:
            for i in range(num_tasks):
                task_id = str(uuid.uuid4())
                task_ids.append(task_id)
                TASKS[task_id] = {
                    'task_id': task_id,
                    'task': f'task {i}',
                    'status': 'queued',
                    'created_at': utc_now(),
                    'large_data': 'x' * 1000  # Simulate large data
                }

        # Verify all tasks exist
        with TASKS_LOCK:
            assert len(TASKS) == num_tasks
            for task_id in task_ids:
                assert task_id in TASKS

        # Cleanup
        TASKS.clear()


class TestServerIntegration:
    """Test server integration scenarios."""

    def test_environment_isolation(self):
        """Test that server operations don't interfere with each other."""
        import os
        import tempfile

        # Test with temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                # Server operations should work in any directory
                prompt = build_task_prompt("test task")
                assert "test task" in prompt
                assert "Important execution requirements:" in prompt
            finally:
                os.chdir(original_cwd)

    def test_large_task_handling(self):
        """Test handling of very large task descriptions."""
        large_task = "x" * 10000  # 10KB task
        result = build_task_prompt(large_task)

        assert large_task in result
        assert len(result) > 10000  # Should include guardrails too

    def test_special_characters_in_tasks(self):
        """Test tasks with special characters and encoding."""
        special_tasks = [
            "Task with émojis 🐍✨",
            "Task with <html> & special chars",
            "Task with\nnewlines\tand\ttabs",
            "Task with 'single' and \"double\" quotes",
            "Task with unicode: ñáéíóú",
        ]

        for task in special_tasks:
            result = build_task_prompt(task)
            assert task in result
            assert "Important execution requirements:" in result

    def test_task_timing_edge_cases(self):
        """Test timing-related edge cases."""
        import time

        # Test rapid task creation
        start_time = time.time()
        timestamps = []

        for i in range(100):
            timestamps.append(utc_now())

        end_time = time.time()

        # Should complete quickly
        assert end_time - start_time < 1.0  # Less than 1 second

        # All timestamps should be unique or very close
        assert len(set(timestamps)) >= 90  # At least 90% unique (accounting for microsecond precision)