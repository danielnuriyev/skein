#!/usr/bin/env python3
"""
Dagster Tool for Goose - Provides Dagster pipeline and backfill operations via GraphQL API.

This tool allows Goose to interact with Dagster pipelines by providing functions to:
- Launch pipeline runs
- Execute backfills
- Check pipeline status
- List available pipelines

Uses Dagster's GraphQL API for direct communication instead of CLI commands.
Requires Dagster webserver to be running (typically at http://localhost:3000/graphql).

Usage in Goose prompts:
- "Launch the ETL pipeline: run_dagster_pipeline('etl_pipeline')"
- "Execute a backfill: run_dagster_backfill('daily_partition_set', ['2023-01-01', '2023-12-31'])"
- "Check pipeline status: check_dagster_pipeline_status('run-123')"
"""

import json
import os
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class DagsterTool:
    """Tool for interacting with Dagster pipelines and backfills via GraphQL API."""

    def __init__(self, graphql_url: str = "http://localhost:3000/graphql"):
        """
        Initialize the Dagster tool with GraphQL endpoint.

        Args:
            graphql_url: URL of Dagster GraphQL endpoint.
                        Defaults to http://localhost:3000/graphql (typical Dagster webserver).
        """
        self.graphql_url = graphql_url
        self._test_connection()

    def _test_connection(self) -> None:
        """Test connection to Dagster GraphQL endpoint."""
        try:
            query = """
            query {
              version
            }
            """
            response = self._execute_query(query)
            if "errors" in response:
                print(f"Warning: Dagster GraphQL connection test failed: {response['errors']}")
            else:
                print("Dagster GraphQL connection established")
        except Exception as e:
            print(f"Warning: Could not connect to Dagster GraphQL at {self.graphql_url}: {e}")

    def _execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        Execute a GraphQL query/mutation.

        Args:
            query: GraphQL query string
            variables: Optional variables for the query

        Returns:
            Parsed JSON response
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = {"Content-Type": "application/json"}

        req = Request(
            self.graphql_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            return {"errors": [{"message": str(e)}]}

    def list_pipelines(self, repository_name: str = "default") -> Dict:
        """
        List all pipelines in a Dagster repository.

        Args:
            repository_name: Name of the Dagster repository

        Returns:
            Dict with 'pipelines' list and 'error' message if any
        """
        query = """
        query ListPipelines($repositoryName: String!) {
          repositoriesOrError {
            ... on RepositoryConnection {
              nodes {
                name
                pipelines {
                  name
                  description
                }
              }
            }
            ... on PythonError {
              message
            }
          }
        }
        """

        variables = {"repositoryName": repository_name}
        response = self._execute_query(query, variables)

        if "errors" in response:
            return {
                "success": False,
                "error": f"GraphQL error: {response['errors']}",
                "pipelines": [],
            }

        try:
            repositories = response["data"]["repositoriesOrError"]
            if "nodes" in repositories:
                for repo in repositories["nodes"]:
                    if repo["name"] == repository_name:
                        pipelines = [
                            {
                                "name": pipeline["name"],
                                "description": pipeline.get("description", ""),
                            }
                            for pipeline in repo["pipelines"]
                        ]
                        return {
                            "success": True,
                            "pipelines": pipelines,
                            "repository": repository_name,
                        }

            return {
                "success": False,
                "error": f"Repository '{repository_name}' not found",
                "pipelines": [],
            }
        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"Failed to parse response: {e}", "pipelines": []}

    def launch_pipeline(
        self,
        pipeline_name: str,
        repository_name: str = "__repository__",
        run_config: Optional[Dict] = None,
        run_id: Optional[str] = None,
    ) -> Dict:
        """
        Launch a Dagster pipeline run.

        Args:
            pipeline_name: Name of the pipeline to run
            repository_name: Repository name (defaults to "__repository__" for single repo setups)
            run_config: Optional run configuration dictionary
            run_id: Optional specific run ID to use

        Returns:
            Dict with run details and success status
        """
        mutation = """
        mutation LaunchPipelineExecution($executionParams: ExecutionParams!) {
          launchPipelineExecution(executionParams: $executionParams) {
            __typename
            ... on LaunchPipelineExecutionSuccess {
              run {
                runId
                status
              }
            }
            ... on PipelineNotFoundError {
              message
            }
            ... on PythonError {
              message
            }
          }
        }
        """

        execution_params = {
            "selector": {"pipelineName": pipeline_name, "repositoryName": repository_name}
        }

        if run_config:
            execution_params["runConfigData"] = run_config

        if run_id:
            execution_params["executionMetadata"] = {"runId": run_id}

        variables = {"executionParams": execution_params}
        response = self._execute_query(mutation, variables)

        if "errors" in response:
            return {
                "success": False,
                "error": f"GraphQL error: {response['errors']}",
            }

        try:
            result = response["data"]["launchPipelineExecution"]
            if result["__typename"] == "LaunchPipelineExecutionSuccess":
                run = result["run"]
                return {
                    "success": True,
                    "message": f"Pipeline {pipeline_name} launched successfully",
                    "run_id": run["runId"],
                    "status": run["status"],
                }
            else:
                return {
                    "success": False,
                    "error": result.get("message", "Unknown error"),
                }
        except (KeyError, TypeError) as e:
            return {
                "success": False,
                "error": f"Failed to parse response: {e}",
            }

    def run_backfill(
        self, partition_set_name: str, partition_names: List[str], from_failure: bool = False
    ) -> Dict:
        """
        Run a backfill for a Dagster partition set.

        Args:
            partition_set_name: Name of the partition set
            partition_names: List of partition names to backfill
            from_failure: Whether to backfill from last failure point

        Returns:
            Dict with backfill details and success status
        """
        mutation = """
        mutation LaunchPartitionBackfill($backfillParams: LaunchBackfillParams!) {
          launchPartitionBackfill(backfillParams: $backfillParams) {
            __typename
            ... on LaunchBackfillSuccess {
              backfillId
            }
            ... on PartitionSetNotFoundError {
              message
            }
            ... on PythonError {
              message
            }
          }
        }
        """

        variables = {
            "backfillParams": {
                "partitionSetName": partition_set_name,
                "partitionNames": partition_names,
                "fromFailure": from_failure,
            }
        }

        response = self._execute_query(mutation, variables)

        if "errors" in response:
            return {
                "success": False,
                "error": f"GraphQL error: {response['errors']}",
                "partition_set": partition_set_name,
                "partitions": partition_names,
            }

        try:
            result = response["data"]["launchPartitionBackfill"]
            if result["__typename"] == "LaunchBackfillSuccess":
                return {
                    "success": True,
                    "message": "Backfill launched successfully",
                    "backfill_id": result["backfillId"],
                    "partition_set": partition_set_name,
                    "partitions": partition_names,
                    "from_failure": from_failure,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("message", "Unknown error"),
                    "partition_set": partition_set_name,
                    "partitions": partition_names,
                }
        except (KeyError, TypeError) as e:
            return {
                "success": False,
                "error": f"Failed to parse response: {e}",
                "partition_set": partition_set_name,
                "partitions": partition_names,
            }

    def get_pipeline_status(self, run_id: str) -> Dict:
        """
        Get the status of a pipeline run.

        Args:
            run_id: The run ID to check

        Returns:
            Dict with status information
        """
        query = """
        query RunStatus($runId: ID!) {
          runOrError(runId: $runId) {
            __typename
            ... on Run {
              runId
              status
              startTime
              endTime
              mode
              tags {
                key
                value
              }
            }
            ... on RunNotFoundError {
              message
            }
          }
        }
        """

        variables = {"runId": run_id}
        response = self._execute_query(query, variables)

        if "errors" in response:
            return {
                "success": False,
                "error": f"GraphQL error: {response['errors']}",
                "run_id": run_id,
            }

        try:
            result = response["data"]["runOrError"]
            if result["__typename"] == "Run":
                return {
                    "success": True,
                    "run_id": result["runId"],
                    "status": result["status"],
                    "start_time": result.get("startTime"),
                    "end_time": result.get("endTime"),
                    "mode": result.get("mode"),
                    "tags": result.get("tags", []),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("message", "Run not found"),
                    "run_id": run_id,
                }
        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"Failed to parse response: {e}", "run_id": run_id}

    def list_runs(self, pipeline_name: Optional[str] = None, limit: int = 10) -> Dict:
        """
        List recent pipeline runs.

        Args:
            pipeline_name: Optional pipeline name to filter by
            limit: Maximum number of runs to return

        Returns:
            Dict with run information
        """
        query = """
        query Runs($filter: RunsFilter, $limit: Int) {
          runsOrError(filter: $filter, limit: $limit) {
            __typename
            ... on Runs {
              results {
                runId
                pipelineName
                status
                startTime
                endTime
                mode
              }
            }
            ... on PythonError {
              message
            }
          }
        }
        """

        filter_dict = {}
        if pipeline_name:
            filter_dict["pipelineName"] = pipeline_name

        variables = {"filter": filter_dict, "limit": limit}

        response = self._execute_query(query, variables)

        if "errors" in response:
            return {"success": False, "error": f"GraphQL error: {response['errors']}", "runs": []}

        try:
            result = response["data"]["runsOrError"]
            if result["__typename"] == "Runs":
                runs = [
                    {
                        "run_id": run["runId"],
                        "pipeline_name": run["pipelineName"],
                        "status": run["status"],
                        "start_time": run.get("startTime"),
                        "end_time": run.get("endTime"),
                        "mode": run.get("mode"),
                    }
                    for run in result["results"]
                ]
                return {"success": True, "runs": runs, "count": len(runs)}
            else:
                return {
                    "success": False,
                    "error": result.get("message", "Unknown error"),
                    "runs": [],
                }
        except (KeyError, TypeError) as e:
            return {"success": False, "error": f"Failed to parse response: {e}", "runs": []}


# Convenience functions for easy use in Goose prompts
_dagster_tool = DagsterTool()


def run_dagster_pipeline(
    pipeline_name: str, repository_name: str = "__repository__", run_config: dict = None
):
    """Convenience function to run a Dagster pipeline."""
    return _dagster_tool.launch_pipeline(pipeline_name, repository_name, run_config)


def run_dagster_backfill(
    partition_set_name: str, partition_names: list, from_failure: bool = False
):
    """Convenience function to run a Dagster backfill."""
    return _dagster_tool.run_backfill(partition_set_name, partition_names, from_failure)


def check_dagster_pipeline_status(run_id: str):
    """Convenience function to check pipeline run status."""
    return _dagster_tool.get_pipeline_status(run_id)


def list_dagster_pipelines(repository_name: str = "default"):
    """Convenience function to list available pipelines."""
    return _dagster_tool.list_pipelines(repository_name)


def list_dagster_runs(pipeline_name: str = None, limit: int = 10):
    """Convenience function to list recent pipeline runs."""
    return _dagster_tool.list_runs(pipeline_name, limit)


if __name__ == "__main__":
    # Example usage
    tool = DagsterTool()

    # List pipelines
    result = tool.list_pipelines("pipelines/my_pipeline.py")
    print("Pipelines:", result)

    # Launch a pipeline
    result = tool.launch_pipeline("pipelines/my_pipeline.py", "my_pipeline", "config/prod.yaml")
    print("Launch result:", result)

    # Run a backfill
    result = tool.run_backfill("pipelines/my_pipeline.py", "my_pipeline", "2023-01-01,2023-12-31")
    print("Backfill result:", result)
