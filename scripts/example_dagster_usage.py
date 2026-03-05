#!/usr/bin/env python3
"""
Example usage of the Dagster tool for Goose.

This script demonstrates how to use the dagster_tool.py functions
that are available to Goose for pipeline operations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dagster_tool import (
    run_dagster_pipeline,
    run_dagster_backfill,
    check_dagster_pipeline_status,
    list_dagster_pipelines,
    list_dagster_runs
)

def demo_pipeline_operations():
    """Demonstrate various Dagster operations."""

    print("Dagster Tool Demo (GraphQL API)")
    print("=" * 50)

    # Example pipeline and repository names (adjust for your Dagster setup)
    repository_name = "default"  # Usually "__repository__" for single repo setups
    pipeline_name = "my_pipeline"
    partition_set_name = "my_partition_set"

    print(f"Repository: {repository_name}")
    print(f"Pipeline: {pipeline_name}")
    print(f"Partition Set: {partition_set_name}")
    print()

    # 1. List available pipelines
    print("1. Listing pipelines...")
    try:
        result = list_dagster_pipelines(repository_name)
        if result['success']:
            pipelines = result['pipelines']
            print(f"Success: Found {len(pipelines)} pipelines:")
            for pipeline in pipelines[:5]:  # Show first 5
                print(f"  - {pipeline['name']}: {pipeline.get('description', 'No description')}")
            if len(pipelines) > 5:
                print(f"  ... and {len(pipelines) - 5} more")
        else:
            print(f"Error: {result['error']}")
    except Exception as e:
        print(f"Exception: {e}")
    print()

    # 2. Launch a pipeline (commented out to avoid actual execution)
    print("2. Launching pipeline...")
    print("   (Skipped in demo - uncomment to run)")
    # Example run config
    # run_config = {
    #     "solids": {
    #         "my_solid": {
    #             "config": {"param": "value"}
    #         }
    #     }
    # }
    # result = run_dagster_pipeline(pipeline_name, repository_name, run_config)
    # print(f"Result: {result}")
    print()

    # 3. Run a backfill (commented out to avoid actual execution)
    print("3. Running backfill...")
    print("   (Skipped in demo - uncomment to run)")
    # result = run_dagster_backfill(partition_set_name, ["2023-01-01", "2023-12-31"])
    # print(f"Result: {result}")
    print()

    # 4. List recent runs
    print("4. Listing recent runs...")
    try:
        result = list_dagster_runs(limit=5)
        if result['success']:
            runs = result['runs']
            print(f"Success: Found {len(runs)} recent runs:")
            for run in runs:
                print(f"  - {run['run_id']}: {run['pipeline_name']} ({run['status']})")
        else:
            print(f"Error: {result['error']}")
    except Exception as e:
        print(f"Exception: {e}")
    print()

    # 5. Check pipeline status (would need a real run_id)
    print("5. Checking pipeline status...")
    print("   (Requires real run_id - demo shows API)")
    # result = check_dagster_pipeline_status("run-123")
    # print(f"Result: {result}")
    print()

    print("Demo complete! GraphQL-based functions are ready for use in Goose tasks.")


if __name__ == "__main__":
    demo_pipeline_operations()