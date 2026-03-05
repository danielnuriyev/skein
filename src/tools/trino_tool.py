#!/usr/bin/env python3
"""
Trino Tool for Goose - Provides integration with Trino.

This tool allows Goose to interact with Trino to:
- List databases (catalogs and schemas)
- Get CREATE TABLE statements for tables

Usage in Goose prompts:
- "List all Trino databases: list_trino_databases()"
- "Get the CREATE TABLE statement for Trino table my_table: get_trino_create_statement('my_catalog', 'my_schema', 'my_table')"
"""

import json
import os
import urllib.request
from typing import Any, Dict, List


class TrinoTool:
    """Tool for interacting with Trino."""

    def __init__(self):
        self.trino_host = os.environ.get("TRINO_HOST", "http://localhost:8080")
        self.trino_user = os.environ.get("TRINO_USER", "goose")

    def _execute_query(self, query: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.trino_host}/v1/statement",
            data=query.encode("utf-8"),
            headers={"X-Trino-User": self.trino_user},
        )
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))

            # Trino queries are async, need to follow nextUri
            rows = []
            columns = []
            while "nextUri" in result:
                if "data" in result:
                    rows.extend(result["data"])
                if "columns" in result and not columns:
                    columns = result["columns"]

                req = urllib.request.Request(result["nextUri"])
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode("utf-8"))

            if "data" in result:
                rows.extend(result["data"])
            if "columns" in result and not columns:
                columns = result["columns"]

            if "error" in result:
                return {"success": False, "error": result["error"]}

            return {"success": True, "columns": columns, "rows": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_databases(self) -> List[str]:
        # Returns catalog.schema format
        catalogs_res = self._execute_query("SHOW CATALOGS")
        if not catalogs_res.get("success"):
            return [f"Error: {catalogs_res.get('error')}"]

        catalogs = [row[0] for row in catalogs_res.get("rows", [])]
        dbs = []
        for cat in catalogs:
            schemas_res = self._execute_query(f"SHOW SCHEMAS FROM {cat}")
            if schemas_res.get("success"):
                for row in schemas_res.get("rows", []):
                    schema = row[0]
                    if schema not in ("information_schema", "mysql"):
                        dbs.append(f"{cat}.{schema}")
        return dbs

    def get_create_statement(self, catalog: str, schema: str, table: str) -> str:
        res = self._execute_query(f"SHOW CREATE TABLE {catalog}.{schema}.{table}")
        if not res.get("success"):
            return f"Error: {res.get('error')}"

        rows = res.get("rows", [])
        if not rows:
            return "Error: Table not found or empty response."

        return rows[0][0]


# --- Convenience functions for Goose ---
_trino_tool = TrinoTool()


def list_trino_databases() -> List[str]:
    """List all databases (catalog.schema) in Trino."""
    return _trino_tool.list_databases()


def get_trino_create_statement(catalog: str, schema: str, table: str) -> str:
    """Get the CREATE TABLE statement for a Trino table."""
    return _trino_tool.get_create_statement(catalog, schema, table)


if __name__ == "__main__":
    pass
