#!/usr/bin/env python3
"""
AWS Athena Tool for Goose - Provides integration with AWS Athena.

This tool allows Goose to interact with AWS Athena to:
- List databases
- Get CREATE TABLE statements for tables

Usage in Goose prompts:
- "List all Athena databases: list_athena_databases()"
- "Get the CREATE TABLE statement for Athena table my_table: get_athena_create_statement('my_db', 'my_table')"
"""

import os
import time
from typing import List, Optional

try:
    import boto3
except ImportError:
    boto3 = None


class AthenaTool:
    """Tool for interacting with AWS Athena."""

    def list_databases(self, catalog_name: str = "AwsDataCatalog") -> List[str]:
        if not boto3:
            return ["Error: boto3 not installed"]
        try:
            client = boto3.client("athena")
            response = client.list_databases(CatalogName=catalog_name)
            return [db.get("Name") for db in response.get("DatabaseList", [])]
        except Exception as e:
            return [f"Error listing Athena databases: {str(e)}"]

    def get_create_statement(
        self, database: str, table: str, s3_output: Optional[str] = None
    ) -> str:
        if not boto3:
            return "Error: boto3 not installed"

        s3_output = s3_output or os.environ.get("ATHENA_S3_OUTPUT")
        if not s3_output:
            return "Error: ATHENA_S3_OUTPUT env var or s3_output parameter is required for Athena queries"

        try:
            client = boto3.client("athena")
            query = f"SHOW CREATE TABLE `{database}`.`{table}`"

            response = client.start_query_execution(
                QueryString=query, ResultConfiguration={"OutputLocation": s3_output}
            )
            exec_id = response["QueryExecutionId"]

            # Wait for query to complete
            while True:
                status_res = client.get_query_execution(QueryExecutionId=exec_id)
                status = status_res["QueryExecution"]["Status"]["State"]
                if status in ["SUCCEEDED", "FAILED", "CANCELLED"]:
                    break
                time.sleep(1)

            if status != "SUCCEEDED":
                reason = status_res["QueryExecution"]["Status"].get("StateChangeReason", "")
                return f"Error: Query {status} - {reason}"

            results = client.get_query_results(QueryExecutionId=exec_id)
            rows = results.get("ResultSet", {}).get("Rows", [])

            # First row is typically header, subsequent rows contain the actual CREATE TABLE chunks
            if not rows:
                return "Error: No results returned"

            create_stmt = "\n".join(
                [row["Data"][0].get("VarCharValue", "") for row in rows if row.get("Data")]
            )
            return create_stmt.strip()
        except Exception as e:
            return f"Error retrieving Athena create statement: {str(e)}"


# --- Convenience functions for Goose ---
_athena_tool = AthenaTool()


def list_athena_databases(catalog_name: str = "AwsDataCatalog") -> List[str]:
    """List all databases in AWS Athena."""
    return _athena_tool.list_databases(catalog_name)


def get_athena_create_statement(database: str, table: str, s3_output: Optional[str] = None) -> str:
    """Get the CREATE TABLE statement for an Athena table."""
    return _athena_tool.get_create_statement(database, table, s3_output)


if __name__ == "__main__":
    pass
