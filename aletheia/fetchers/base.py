"""Base fetcher interface for data collection.

This module defines the abstract base class and data models for all fetchers
(Kubernetes, Elasticsearch, Prometheus, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


@dataclass
class FetchResult:
    """Result from a fetch operation.

    Attributes:
        source: Name of the data source (e.g., "kubernetes", "elasticsearch")
        data: The fetched data (logs, metrics, traces, etc.)
        summary: Human-readable summary of the data
        count: Number of items fetched
        time_range: Tuple of (start_time, end_time) for the data
        metadata: Additional metadata about the fetch operation
    """

    source: str
    data: Any
    summary: str
    count: int
    time_range: Tuple[datetime, datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert FetchResult to dictionary for serialization.

        Returns:
            Dictionary representation of the FetchResult
        """
        return {
            "source": self.source,
            "data": self.data,
            "summary": self.summary,
            "count": self.count,
            "time_range": (
                self.time_range[0].isoformat(),
                self.time_range[1].isoformat(),
            ),
            "metadata": self.metadata,
        }


class FetchError(Exception):
    """Base exception for fetch operations."""

    pass


class ConnectionError(FetchError):
    """Raised when connection to data source fails."""

    pass


class AuthenticationError(FetchError):
    """Raised when authentication to data source fails."""

    pass


class QueryError(FetchError):
    """Raised when query construction or execution fails."""

    pass


class DataSourceNotFoundError(FetchError):
    """Raised when the requested data source is not found."""

    pass


class BaseFetcher(ABC):
    """Abstract base class for all data fetchers.

    Fetchers are responsible for collecting data from external sources
    (Kubernetes, Elasticsearch, Prometheus, etc.) and returning it in
    a standardized format.

    Subclasses must implement:
        - fetch(): Main data collection method
        - validate_config(): Validate fetcher configuration
        - test_connection(): Test connectivity to data source
        - get_capabilities(): Return fetcher capabilities
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the fetcher with configuration.

        Args:
            config: Configuration dictionary for the fetcher
        """
        self.config = config

    @abstractmethod
    def fetch(
        self,
        time_window: Optional[Tuple[datetime, datetime]] = None,
        **kwargs: Any,
    ) -> FetchResult:
        """Fetch data from the source.

        Args:
            time_window: Optional tuple of (start_time, end_time) to filter data
            **kwargs: Additional fetcher-specific parameters

        Returns:
            FetchResult containing the fetched data

        Raises:
            FetchError: If fetch operation fails
        """
        pass



    @abstractmethod
    def test_connection(self) -> bool:
        """Test connectivity to the data source.

        Returns:
            True if connection successful, False otherwise

        Raises:
            ConnectionError: If connection test fails
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities of this fetcher.

        Returns:
            Dictionary describing fetcher capabilities, e.g.:
            {
                "supports_time_window": True,
                "supports_streaming": False,
                "max_sample_size": 10000,
                "data_types": ["logs", "events"]
            }
        """
        pass

    def __repr__(self) -> str:
        """Return string representation of the fetcher."""
        return f"{self.__class__.__name__}(config={self.config})"
