"""Kusto query loader for Azure Log Analytics."""

import yaml

from aletheia.config import Config, get_config_dir


class KustoQuery:
    """Represents a Kusto query template."""

    def __init__(self, name: str, description: str, query: str):
        self.name = name
        self.description = description
        self.query = query

    def __repr__(self) -> str:
        return f"KustoQuery(name={self.name!r}, description={self.description!r})"

    def to_dict(self) -> dict[str, str]:
        """Convert the query to a dictionary for JSON serialization.

        Returns:
            Dictionary with name, description, and query fields
        """
        return {"name": self.name, "description": self.description, "query": self.query}


class KustoQueryLoader:
    """Loads Kusto query templates from YAML configuration file.

    The loader reads queries from: {config_dir}/custom/azure/kusto_queries.yaml

    Expected YAML format:
    ---
    queries:
      - name: Query Name
        description: Query description
        query: |-
          KQL query template
          with multiple lines
    """

    def __init__(self, config: Config):
        self.config = config
        self.kusto_queries_path = (
            get_config_dir() / "custom" / "azure" / "kusto_queries.yaml"
        )
        self._queries: dict[str, KustoQuery] = {}
        self._load_queries()

    def _load_queries(self) -> None:
        """Load queries from YAML file into dictionary."""
        if not self.kusto_queries_path.exists():
            # No queries file exists, initialize with empty dict
            return

        try:
            with open(self.kusto_queries_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "queries" not in data:
                return

            for query_data in data["queries"]:
                query = KustoQuery(
                    name=query_data["name"],
                    description=query_data["description"],
                    query=query_data["query"],
                )
                self._queries[query.name] = query

        except (yaml.YAMLError, KeyError, TypeError) as e:
            raise ValueError(
                f"Failed to load Kusto queries from {self.kusto_queries_path}: {e}"
            ) from e

    def get_query(self, name: str) -> KustoQuery | None:
        """Get a query by name.

        Args:
            name: The name of the query to retrieve

        Returns:
            KustoQuery object if found, None otherwise
        """
        return self._queries.get(name)

    def get_all_queries(self) -> dict[str, KustoQuery]:
        """Get all loaded queries.

        Returns:
            Dictionary mapping query names to KustoQuery objects
        """
        return self._queries.copy()

    def list_query_names(self) -> list[str]:
        """Get list of all query names.

        Returns:
            List of query names
        """
        return list(self._queries.keys())

    def get_all_queries_as_dicts(self) -> list[dict[str, str]]:
        """Get all queries as list of dictionaries for JSON serialization.

        Returns:
            List of dictionaries, each containing name, description, and query fields
        """
        return [query.to_dict() for query in self._queries.values()]
