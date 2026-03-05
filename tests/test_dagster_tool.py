"""Tests for dagster_tool.py - Dagster pipeline operations via GraphQL API."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from urllib.error import URLError, HTTPError

from src.tools.dagster_tool import DagsterTool


class TestDagsterToolInitialization:
    """Test DagsterTool initialization and connection."""

    @patch('src.tools.dagster_tool.urlopen')
    def test_successful_connection(self, mock_urlopen):
        """Test successful connection to Dagster GraphQL."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"data": {"version": "1.0.0"}}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        tool = DagsterTool()
        assert tool.graphql_url == "http://localhost:3000/graphql"

    @patch('src.tools.dagster_tool.urlopen')
    def test_connection_failure(self, mock_urlopen):
        """Test graceful handling of connection failure."""
        mock_urlopen.side_effect = URLError("Connection refused")

        # Should not raise exception during init
        tool = DagsterTool()
        assert tool.graphql_url == "http://localhost:3000/graphql"

    def test_custom_graphql_url(self):
        """Test custom GraphQL endpoint URL."""
        custom_url = "https://my-dagster-instance.com/graphql"
        tool = DagsterTool(custom_url)
        assert tool.graphql_url == custom_url


class TestGraphQLQueries:
    """Test GraphQL query execution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.urlopen')
    def test_successful_query(self, mock_urlopen):
        """Test successful GraphQL query execution."""
        mock_response = Mock()
        expected_data = {"data": {"test": "value"}}
        mock_response.read.return_value = json.dumps(expected_data).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = self.tool._execute_query("query { test }")

        assert result == expected_data
        mock_urlopen.assert_called_once()

    @patch('src.tools.dagster_tool.urlopen')
    def test_query_with_variables(self, mock_urlopen):
        """Test GraphQL query with variables."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"data": {"result": "ok"}}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        variables = {"param": "value"}
        result = self.tool._execute_query("query Test($param: String) { test(param: $param) }", variables)

        assert result["data"]["result"] == "ok"

    @patch('src.tools.dagster_tool.urlopen')
    def test_http_error(self, mock_urlopen):
        """Test handling of HTTP errors."""
        mock_urlopen.side_effect = HTTPError(None, 500, "Internal Server Error", None, None)

        result = self.tool._execute_query("query { test }")

        assert "errors" in result
        assert len(result["errors"]) == 1

    @patch('src.tools.dagster_tool.urlopen')
    def test_network_error(self, mock_urlopen):
        """Test handling of network errors."""
        mock_urlopen.side_effect = URLError("Network unreachable")

        result = self.tool._execute_query("query { test }")

        assert "errors" in result
        assert len(result["errors"]) == 1


class TestPipelineListing:
    """Test pipeline listing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_list_pipelines_success(self, mock_execute):
        """Test successful pipeline listing."""
        mock_response = {
            "data": {
                "repositoriesOrError": {
                    "nodes": [{
                        "name": "default",
                        "pipelines": [
                            {"name": "pipeline1", "description": "First pipeline"},
                            {"name": "pipeline2", "description": None}
                        ]
                    }]
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.list_pipelines("default")

        assert result["success"] is True
        assert len(result["pipelines"]) == 2
        assert result["pipelines"][0]["name"] == "pipeline1"
        assert result["pipelines"][0]["description"] == "First pipeline"
        assert result["pipelines"][1]["description"] is None

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_list_pipelines_repository_not_found(self, mock_execute):
        """Test pipeline listing when repository doesn't exist."""
        mock_response = {
            "data": {
                "repositoriesOrError": {
                    "nodes": []
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.list_pipelines("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_list_pipelines_graphql_error(self, mock_execute):
        """Test pipeline listing with GraphQL errors."""
        mock_execute.return_value = {"errors": [{"message": "GraphQL error"}]}

        result = self.tool.list_pipelines("default")

        assert result["success"] is False
        assert "GraphQL error" in result["error"]

    def test_list_pipelines_empty_repository(self):
        """Test pipeline listing with empty repository name."""
        result = self.tool.list_pipelines("")

        # Should handle empty string gracefully
        assert isinstance(result, dict)
        assert "success" in result


class TestPipelineLaunching:
    """Test pipeline launching functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_launch_pipeline_success(self, mock_execute):
        """Test successful pipeline launch."""
        mock_response = {
            "data": {
                "launchPipelineExecution": {
                    "__typename": "LaunchPipelineExecutionSuccess",
                    "run": {
                        "runId": "test-run-123",
                        "status": "STARTING"
                    }
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.launch_pipeline("test_pipeline", "default")

        assert result["success"] is True
        assert result["run_id"] == "test-run-123"
        assert result["status"] == "STARTING"
        assert "launched successfully" in result["message"]

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_launch_pipeline_with_config(self, mock_execute):
        """Test pipeline launch with run configuration."""
        mock_response = {
            "data": {
                "launchPipelineExecution": {
                    "__typename": "LaunchPipelineExecutionSuccess",
                    "run": {
                        "runId": "config-run-456",
                        "status": "STARTING"
                    }
                }
            }
        }
        mock_execute.return_value = mock_response

        run_config = {"solids": {"my_solid": {"config": {"param": "value"}}}}
        result = self.tool.launch_pipeline("test_pipeline", "default", run_config)

        assert result["success"] is True
        assert result["run_id"] == "config-run-456"

        # Verify the config was passed in the GraphQL call
        call_args = mock_execute.call_args
        variables = call_args[1]["executionParams"]  # kwargs
        assert "runConfigData" in variables
        assert variables["runConfigData"] == run_config

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_launch_pipeline_with_run_id(self, mock_execute):
        """Test pipeline launch with specific run ID."""
        mock_response = {
            "data": {
                "launchPipelineExecution": {
                    "__typename": "LaunchPipelineExecutionSuccess",
                    "run": {
                        "runId": "custom-run-789",
                        "status": "STARTING"
                    }
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.launch_pipeline("test_pipeline", "default", run_id="custom-run-789")

        assert result["success"] is True
        assert result["run_id"] == "custom-run-789"

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_launch_pipeline_not_found(self, mock_execute):
        """Test pipeline launch when pipeline doesn't exist."""
        mock_response = {
            "data": {
                "launchPipelineExecution": {
                    "__typename": "PipelineNotFoundError",
                    "message": "Pipeline 'nonexistent' not found"
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.launch_pipeline("nonexistent", "default")

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_launch_pipeline_graphql_error(self, mock_execute):
        """Test pipeline launch with GraphQL errors."""
        mock_execute.return_value = {"errors": [{"message": "Invalid syntax"}]}

        result = self.tool.launch_pipeline("test_pipeline", "default")

        assert result["success"] is False
        assert "GraphQL error" in result["error"]


class TestBackfillOperations:
    """Test backfill functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_run_backfill_success(self, mock_execute):
        """Test successful backfill execution."""
        mock_response = {
            "data": {
                "launchPartitionBackfill": {
                    "__typename": "LaunchBackfillSuccess",
                    "backfillId": "backfill-123"
                }
            }
        }
        mock_execute.return_value = mock_response

        partition_names = ["2023-01-01", "2023-01-02"]
        result = self.tool.run_backfill("daily_partition_set", partition_names, from_failure=True)

        assert result["success"] is True
        assert result["backfill_id"] == "backfill-123"
        assert result["partition_set"] == "daily_partition_set"
        assert result["partitions"] == partition_names
        assert result["from_failure"] is True

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_run_backfill_partition_set_not_found(self, mock_execute):
        """Test backfill with non-existent partition set."""
        mock_response = {
            "data": {
                "launchPartitionBackfill": {
                    "__typename": "PartitionSetNotFoundError",
                    "message": "Partition set 'invalid' not found"
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.run_backfill("invalid", ["2023-01-01"])

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_run_backfill_empty_partitions(self):
        """Test backfill with empty partition list."""
        result = self.tool.run_backfill("test_set", [])

        # Should handle empty list gracefully
        assert isinstance(result, dict)
        assert "success" in result


class TestPipelineStatus:
    """Test pipeline status checking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_get_pipeline_status_success(self, mock_execute):
        """Test successful pipeline status retrieval."""
        mock_response = {
            "data": {
                "runOrError": {
                    "__typename": "Run",
                    "runId": "test-run-123",
                    "status": "SUCCESS",
                    "startTime": 1640995200.0,
                    "endTime": 1640995260.0,
                    "mode": "default",
                    "tags": [{"key": "user", "value": "test"}]
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.get_pipeline_status("test-run-123")

        assert result["success"] is True
        assert result["run_id"] == "test-run-123"
        assert result["status"] == "SUCCESS"
        assert result["mode"] == "default"
        assert result["tags"] == [{"key": "user", "value": "test"}]

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_get_pipeline_status_not_found(self, mock_execute):
        """Test pipeline status for non-existent run."""
        mock_response = {
            "data": {
                "runOrError": {
                    "__typename": "RunNotFoundError",
                    "message": "Run 'nonexistent' not found"
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.get_pipeline_status("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_get_pipeline_status_empty_run_id(self):
        """Test pipeline status with empty run ID."""
        result = self.tool.get_pipeline_status("")

        # Should handle empty string gracefully
        assert isinstance(result, dict)
        assert "success" in result


class TestRunListing:
    """Test run listing functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_list_runs_success(self, mock_execute):
        """Test successful run listing."""
        mock_response = {
            "data": {
                "runsOrError": {
                    "__typename": "Runs",
                    "results": [
                        {
                            "runId": "run-1",
                            "pipelineName": "pipeline1",
                            "status": "SUCCESS",
                            "startTime": 1640995200.0,
                            "endTime": 1640995260.0,
                            "mode": "default"
                        },
                        {
                            "runId": "run-2",
                            "pipelineName": "pipeline2",
                            "status": "FAILED",
                            "startTime": 1640995300.0,
                            "endTime": None,
                            "mode": "dev"
                        }
                    ]
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.list_runs(limit=10)

        assert result["success"] is True
        assert len(result["runs"]) == 2
        assert result["runs"][0]["run_id"] == "run-1"
        assert result["runs"][0]["pipeline_name"] == "pipeline1"
        assert result["runs"][1]["status"] == "FAILED"

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_list_runs_filtered_by_pipeline(self, mock_execute):
        """Test run listing filtered by pipeline name."""
        mock_response = {
            "data": {
                "runsOrError": {
                    "__typename": "Runs",
                    "results": [
                        {
                            "runId": "run-1",
                            "pipelineName": "target_pipeline",
                            "status": "SUCCESS"
                        }
                    ]
                }
            }
        }
        mock_execute.return_value = mock_response

        result = self.tool.list_runs(pipeline_name="target_pipeline", limit=5)

        assert result["success"] is True
        assert len(result["runs"]) == 1
        assert result["runs"][0]["pipeline_name"] == "target_pipeline"

        # Verify the filter was applied in the GraphQL query
        call_args = mock_execute.call_args
        variables = call_args[1]  # kwargs
        assert variables["filter"]["pipelineName"] == "target_pipeline"


class TestConcurrency:
    """Test concurrent operations and thread safety."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    @patch('src.tools.dagster_tool.DagsterTool._execute_query')
    def test_concurrent_pipeline_launches(self, mock_execute):
        """Test multiple concurrent pipeline launches."""
        import threading

        mock_execute.return_value = {
            "data": {
                "launchPipelineExecution": {
                    "__typename": "LaunchPipelineExecutionSuccess",
                    "run": {
                        "runId": "concurrent-run",
                        "status": "STARTING"
                    }
                }
            }
        }

        results = []
        errors = []

        def launch_worker(pipeline_name):
            """Worker function for concurrent launches."""
            try:
                result = self.tool.launch_pipeline(pipeline_name, "default")
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = []
        pipeline_names = [f"pipeline-{i}" for i in range(5)]

        for name in pipeline_names:
            t = threading.Thread(target=launch_worker, args=(name,))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Verify results
        assert len(results) == 5
        assert len(errors) == 0
        for result in results:
            assert result["success"] is True
            assert "run_id" in result

    @pytest.mark.parametrize("num_threads", [1, 3, 5])
    def test_concurrent_status_checks(self, num_threads):
        """Test concurrent pipeline status checks."""
        import threading

        with patch.object(self.tool, '_execute_query') as mock_execute:
            mock_execute.return_value = {
                "data": {
                    "runOrError": {
                        "__typename": "Run",
                        "runId": "test-run",
                        "status": "SUCCESS"
                    }
                }
            }

            results = []
            errors = []

            def status_worker(run_id):
                """Worker function for concurrent status checks."""
                try:
                    result = self.tool.get_pipeline_status(run_id)
                    results.append(result)
                except Exception as e:
                    errors.append(str(e))

            # Create threads
            threads = []
            run_ids = [f"run-{i}" for i in range(num_threads)]

            for run_id in run_ids:
                t = threading.Thread(target=status_worker, args=(run_id,))
                threads.append(t)

            # Execute concurrently
            for t in threads:
                t.start()

            for t in threads:
                t.join()

            # Verify results
            assert len(results) == num_threads
            assert len(errors) == 0


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = DagsterTool()

    def test_empty_pipeline_name(self):
        """Test operations with empty pipeline name."""
        result = self.tool.launch_pipeline("", "default")
        assert isinstance(result, dict)
        assert "success" in result

    def test_none_config(self):
        """Test pipeline launch with None config."""
        with patch.object(self.tool, '_execute_query') as mock_execute:
            mock_execute.return_value = {
                "data": {
                    "launchPipelineExecution": {
                        "__typename": "LaunchPipelineExecutionSuccess",
                        "run": {"runId": "test", "status": "STARTING"}
                    }
                }
            }

            result = self.tool.launch_pipeline("test", "default", None)
            assert result["success"] is True

    def test_large_run_config(self):
        """Test pipeline launch with large configuration."""
        large_config = {
            "solids": {
                f"solid_{i}": {
                    "config": {"param": f"value_{i}"}
                }
                for i in range(100)
            }
        }

        with patch.object(self.tool, '_execute_query') as mock_execute:
            mock_execute.return_value = {
                "data": {
                    "launchPipelineExecution": {
                        "__typename": "LaunchPipelineExecutionSuccess",
                        "run": {"runId": "large-config-run", "status": "STARTING"}
                    }
                }
            }

            result = self.tool.launch_pipeline("test_pipeline", "default", large_config)
            assert result["success"] is True
            assert result["run_id"] == "large-config-run"

    def test_unicode_pipeline_names(self):
        """Test pipeline operations with unicode characters."""
        unicode_name = "测试_pipeline_ñáéíóú"

        with patch.object(self.tool, '_execute_query') as mock_execute:
            mock_execute.return_value = {
                "data": {
                    "launchPipelineExecution": {
                        "__typename": "LaunchPipelineExecutionSuccess",
                        "run": {"runId": "unicode-run", "status": "STARTING"}
                    }
                }
            }

            result = self.tool.launch_pipeline(unicode_name, "default")
            assert result["success"] is True

    def test_extremely_long_run_id(self):
        """Test operations with extremely long run IDs."""
        long_run_id = "run-" + "a" * 1000

        with patch.object(self.tool, '_execute_query') as mock_execute:
            mock_execute.return_value = {
                "data": {
                    "runOrError": {
                        "__typename": "Run",
                        "runId": long_run_id,
                        "status": "SUCCESS"
                    }
                }
            }

            result = self.tool.get_pipeline_status(long_run_id)
            assert result["success"] is True
            assert result["run_id"] == long_run_id