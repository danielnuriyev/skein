#!/usr/bin/env python3
"""
AWS Glue Tool for Goose - Provides integration with AWS Glue Data Catalog.

This tool allows Goose to list databases in the AWS Glue Data Catalog.

Usage in Goose prompts:
- "List all Glue databases: list_glue_databases()"
"""

from typing import List

try:
    import boto3
except ImportError:
    boto3 = None


class GlueTool:
    """Tool for interacting with AWS Glue."""

    def list_databases(self) -> List[str]:
        if not boto3:
            return ["Error: boto3 not installed"]
        try:
            client = boto3.client("glue")
            paginator = client.get_paginator("get_databases")
            dbs = []
            for page in paginator.paginate():
                for db in page.get("DatabaseList", []):
                    dbs.append(db.get("Name"))
            return dbs
        except Exception as e:
            return [f"Error listing Glue databases: {str(e)}"]


# --- Convenience functions for Goose ---
_glue_tool = GlueTool()


def list_glue_databases() -> List[str]:
    """List all databases in AWS Glue."""
    return _glue_tool.list_databases()


if __name__ == "__main__":
    pass
