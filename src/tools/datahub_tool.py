#!/usr/bin/env python3
"""
DataHub Tool for Goose - Provides integration with DataHub.

This tool allows Goose to interact with DataHub to:
- Search datasets
- Get table descriptions
- Get column descriptions

Usage in Goose prompts:
- "Search DataHub for a table: search_datahub_dataset('users')"
- "Get table description from DataHub: get_datahub_table_description('urn:...')"
- "Get column description from DataHub: get_datahub_column_description('urn:...', 'user_id')"
"""

import json
import os
import urllib.request
from typing import Dict, List


class DataHubTool:
    """Tool for interacting with DataHub."""

    def __init__(self):
        self.datahub_url = os.environ.get("DATAHUB_URL", "http://localhost:8080/api/graphql")
        self.datahub_token = os.environ.get("DATAHUB_TOKEN", "")

    def _execute_graphql(self, query: str, variables: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.datahub_token:
            headers["Authorization"] = f"Bearer {self.datahub_token}"

        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")

        req = urllib.request.Request(self.datahub_url, data=payload, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            return {"errors": [{"message": str(e)}]}

    def search_dataset(self, query: str) -> List[Dict[str, str]]:
        graphql_query = """
        query search($input: SearchInput!) {
          search(input: $input) {
            searchResults {
              entity {
                ... on Dataset {
                  urn
                  name
                  platform {
                    name
                  }
                }
              }
            }
          }
        }
        """
        variables = {"input": {"type": "DATASET", "query": query, "start": 0, "count": 10}}
        res = self._execute_graphql(graphql_query, variables)
        try:
            results = []
            for r in res.get("data", {}).get("search", {}).get("searchResults", []):
                entity = r.get("entity", {})
                platform_name = "unknown"
                if entity.get("platform"):
                    platform_name = entity["platform"].get("name", "unknown")
                results.append(
                    {
                        "urn": entity.get("urn", ""),
                        "name": entity.get("name", ""),
                        "platform": platform_name,
                    }
                )
            return results
        except Exception as e:
            return [{"error": f"Failed to parse DataHub search response: {str(e)}"}]

    def get_table_description(self, urn: str) -> str:
        query = """
        query getDataset($urn: String!) {
          dataset(urn: $urn) {
            properties {
              description
            }
          }
        }
        """
        res = self._execute_graphql(query, {"urn": urn})
        try:
            props = res.get("data", {}).get("dataset", {}).get("properties")
            if props and props.get("description"):
                return props["description"]
            return "No description found."
        except Exception as e:
            return f"Error retrieving dataset properties: {str(e)}"

    def get_column_description(self, urn: str, column_name: str) -> str:
        query = """
        query getDataset($urn: String!) {
          dataset(urn: $urn) {
            schemaMetadata {
              fields {
                fieldPath
                description
              }
            }
          }
        }
        """
        res = self._execute_graphql(query, {"urn": urn})
        try:
            fields = (
                res.get("data", {}).get("dataset", {}).get("schemaMetadata", {}).get("fields", [])
            )
            for field in fields:
                if field.get("fieldPath") == column_name:
                    return field.get("description") or "No description found."
            return f"Column '{column_name}' not found."
        except Exception as e:
            return f"Error retrieving schema metadata: {str(e)}"


# --- Convenience functions for Goose ---
_datahub_tool = DataHubTool()


def search_datahub_dataset(query: str) -> List[Dict[str, str]]:
    """Search for a dataset in DataHub by name."""
    return _datahub_tool.search_dataset(query)


def get_datahub_table_description(urn: str) -> str:
    """Get the description of a table from DataHub using its URN."""
    return _datahub_tool.get_table_description(urn)


def get_datahub_column_description(urn: str, column_name: str) -> str:
    """Get the description of a specific column from a DataHub table using its URN."""
    return _datahub_tool.get_column_description(urn, column_name)


if __name__ == "__main__":
    pass
