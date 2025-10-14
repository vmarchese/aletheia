"""Unit tests for base fetcher interface."""

import pytest
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from aletheia.fetchers.base import (
    BaseFetcher,
    FetchResult,
    FetchError,
    ConnectionError,
    AuthenticationError,
    QueryError,
    DataSourceNotFoundError,
)


# Mock concrete fetcher implementation for testing
class MockFetcher(BaseFetcher):
    """Mock fetcher for testing base class."""

    def __init__(self, config: Dict[str, Any], should_fail: bool = False):
        self.should_fail = should_fail
        self.connection_tested = False
        super().__init__(config)

    def fetch(
        self,
        time_window: Optional[Tuple[datetime, datetime]] = None,
        **kwargs: Any,
    ) -> FetchResult:
        """Mock fetch implementation."""
        if self.should_fail:
            raise FetchError("Mock fetch failed")

        start_time = time_window[0] if time_window else datetime.now() - timedelta(hours=1)
        end_time = time_window[1] if time_window else datetime.now()

        return FetchResult(
            source="mock",
            data={"logs": ["log1", "log2", "log3"]},
            summary="Fetched 3 mock logs",
            count=3,
            time_range=(start_time, end_time),
            metadata={"fetcher": "mock", "kwargs": kwargs},
        )

    def validate_config(self) -> None:
        """Mock config validation."""
        if "endpoint" not in self.config:
            raise ValueError("Missing required config: endpoint")

    def test_connection(self) -> bool:
        """Mock connection test."""
        self.connection_tested = True
        if self.should_fail:
            raise ConnectionError("Mock connection failed")
        return True

    def get_capabilities(self) -> Dict[str, Any]:
        """Mock capabilities."""
        return {
            "supports_time_window": True,
            "supports_streaming": False,
            "max_sample_size": 1000,
            "data_types": ["logs"],
        }


# Test FetchResult dataclass


def test_fetch_result_creation():
    """Test FetchResult can be created with all fields."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    result = FetchResult(
        source="kubernetes",
        data={"logs": ["error1", "error2"]},
        summary="2 errors found",
        count=2,
        time_range=(start, end),
        metadata={"pod": "test-pod"},
    )

    assert result.source == "kubernetes"
    assert result.data == {"logs": ["error1", "error2"]}
    assert result.summary == "2 errors found"
    assert result.count == 2
    assert result.time_range == (start, end)
    assert result.metadata == {"pod": "test-pod"}


def test_fetch_result_default_metadata():
    """Test FetchResult has default empty metadata."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    result = FetchResult(
        source="test",
        data=[],
        summary="empty",
        count=0,
        time_range=(start, end),
    )

    assert result.metadata == {}


def test_fetch_result_to_dict():
    """Test FetchResult can be serialized to dict."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    result = FetchResult(
        source="prometheus",
        data={"metric": "error_rate", "value": 5.3},
        summary="Error rate: 5.3/s",
        count=1,
        time_range=(start, end),
        metadata={"query": "rate(errors[5m])"},
    )

    result_dict = result.to_dict()

    assert result_dict["source"] == "prometheus"
    assert result_dict["data"] == {"metric": "error_rate", "value": 5.3}
    assert result_dict["summary"] == "Error rate: 5.3/s"
    assert result_dict["count"] == 1
    assert result_dict["time_range"] == (start.isoformat(), end.isoformat())
    assert result_dict["metadata"] == {"query": "rate(errors[5m])"}


# Test exception hierarchy


def test_fetch_error_base():
    """Test FetchError can be raised and caught."""
    with pytest.raises(FetchError, match="test error"):
        raise FetchError("test error")


def test_connection_error():
    """Test ConnectionError is a FetchError."""
    with pytest.raises(FetchError):
        raise ConnectionError("connection failed")

    with pytest.raises(ConnectionError, match="connection failed"):
        raise ConnectionError("connection failed")


def test_authentication_error():
    """Test AuthenticationError is a FetchError."""
    with pytest.raises(FetchError):
        raise AuthenticationError("auth failed")

    with pytest.raises(AuthenticationError, match="auth failed"):
        raise AuthenticationError("auth failed")


def test_query_error():
    """Test QueryError is a FetchError."""
    with pytest.raises(FetchError):
        raise QueryError("query failed")

    with pytest.raises(QueryError, match="query failed"):
        raise QueryError("query failed")


def test_data_source_not_found_error():
    """Test DataSourceNotFoundError is a FetchError."""
    with pytest.raises(FetchError):
        raise DataSourceNotFoundError("source not found")

    with pytest.raises(DataSourceNotFoundError, match="source not found"):
        raise DataSourceNotFoundError("source not found")


# Test BaseFetcher abstract class


def test_base_fetcher_initialization():
    """Test BaseFetcher can be initialized with config."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    assert fetcher.config == config


def test_base_fetcher_validates_config_on_init():
    """Test BaseFetcher validates config during initialization."""
    with pytest.raises(ValueError, match="Missing required config: endpoint"):
        MockFetcher({})


def test_base_fetcher_fetch():
    """Test fetch method returns FetchResult."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    result = fetcher.fetch()

    assert isinstance(result, FetchResult)
    assert result.source == "mock"
    assert result.count == 3
    assert result.summary == "Fetched 3 mock logs"


def test_base_fetcher_fetch_with_time_window():
    """Test fetch method accepts time_window parameter."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    result = fetcher.fetch(time_window=(start, end))

    assert result.time_range == (start, end)


def test_base_fetcher_fetch_with_kwargs():
    """Test fetch method accepts additional kwargs."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    result = fetcher.fetch(namespace="production", pod="test-pod")

    assert result.metadata["kwargs"] == {"namespace": "production", "pod": "test-pod"}


def test_base_fetcher_fetch_error():
    """Test fetch raises FetchError on failure."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config, should_fail=True)

    with pytest.raises(FetchError, match="Mock fetch failed"):
        fetcher.fetch()


def test_base_fetcher_test_connection():
    """Test test_connection method works."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    result = fetcher.test_connection()

    assert result is True
    assert fetcher.connection_tested is True


def test_base_fetcher_test_connection_failure():
    """Test test_connection raises ConnectionError on failure."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config, should_fail=True)

    with pytest.raises(ConnectionError, match="Mock connection failed"):
        fetcher.test_connection()


def test_base_fetcher_get_capabilities():
    """Test get_capabilities returns capability dict."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    capabilities = fetcher.get_capabilities()

    assert isinstance(capabilities, dict)
    assert capabilities["supports_time_window"] is True
    assert capabilities["supports_streaming"] is False
    assert capabilities["max_sample_size"] == 1000
    assert capabilities["data_types"] == ["logs"]


def test_base_fetcher_repr():
    """Test __repr__ returns string representation."""
    config = {"endpoint": "http://test.com"}
    fetcher = MockFetcher(config)

    repr_str = repr(fetcher)

    assert "MockFetcher" in repr_str
    assert "config=" in repr_str


# Test abstract method enforcement


def test_base_fetcher_abstract_methods():
    """Test BaseFetcher cannot be instantiated without implementing abstract methods."""

    class IncompleteFetcher(BaseFetcher):
        """Fetcher missing abstract methods."""

        def validate_config(self) -> None:
            pass

    with pytest.raises(TypeError):
        IncompleteFetcher({"endpoint": "test"})


# Test edge cases


def test_fetch_result_with_none_data():
    """Test FetchResult can handle None data."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    result = FetchResult(
        source="test",
        data=None,
        summary="No data",
        count=0,
        time_range=(start, end),
    )

    assert result.data is None
    assert result.count == 0


def test_fetch_result_with_empty_time_range():
    """Test FetchResult with same start and end time."""
    now = datetime.now()

    result = FetchResult(
        source="test",
        data=[],
        summary="Instant query",
        count=0,
        time_range=(now, now),
    )

    assert result.time_range[0] == result.time_range[1]


def test_fetch_result_with_large_data():
    """Test FetchResult can handle large data sets."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    large_data = [f"log_{i}" for i in range(10000)]

    result = FetchResult(
        source="test",
        data=large_data,
        summary="10000 logs",
        count=10000,
        time_range=(start, end),
    )

    assert len(result.data) == 10000
    assert result.count == 10000


def test_fetch_result_with_complex_metadata():
    """Test FetchResult with complex nested metadata."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    complex_metadata = {
        "query": {"type": "dsl", "body": {"match": {"level": "ERROR"}}},
        "filters": ["service:payments", "env:prod"],
        "pagination": {"page": 1, "size": 100},
        "nested": {"deep": {"value": 42}},
    }

    result = FetchResult(
        source="elasticsearch",
        data=[],
        summary="Complex query",
        count=0,
        time_range=(start, end),
        metadata=complex_metadata,
    )

    assert result.metadata["query"]["type"] == "dsl"
    assert result.metadata["nested"]["deep"]["value"] == 42


def test_fetch_result_serialization_preserves_data():
    """Test to_dict preserves all data correctly."""
    start = datetime(2025, 10, 13, 8, 0)
    end = datetime(2025, 10, 13, 10, 0)

    original = FetchResult(
        source="test",
        data={"key": "value", "nested": {"data": [1, 2, 3]}},
        summary="Test",
        count=1,
        time_range=(start, end),
        metadata={"meta": "data"},
    )

    serialized = original.to_dict()

    assert serialized["data"] == {"key": "value", "nested": {"data": [1, 2, 3]}}
    assert serialized["metadata"] == {"meta": "data"}


# Test error message clarity


def test_error_messages_are_descriptive():
    """Test exception messages are clear and helpful."""
    errors = [
        (FetchError("Failed to fetch"), "Failed to fetch"),
        (ConnectionError("Cannot connect to host"), "Cannot connect to host"),
        (AuthenticationError("Invalid credentials"), "Invalid credentials"),
        (QueryError("Malformed query syntax"), "Malformed query syntax"),
        (DataSourceNotFoundError("Source 'test' not found"), "Source 'test' not found"),
    ]

    for error, expected_msg in errors:
        assert str(error) == expected_msg


# Test type safety


def test_fetch_result_type_annotations():
    """Test FetchResult has proper type annotations."""
    import inspect
    from typing import get_type_hints

    hints = get_type_hints(FetchResult)

    assert hints["source"] == str
    assert hints["data"] == Any
    assert hints["summary"] == str
    assert hints["count"] == int
    assert hints["time_range"] == Tuple[datetime, datetime]
    assert hints["metadata"] == Dict[str, Any]


def test_base_fetcher_type_annotations():
    """Test BaseFetcher methods have proper type annotations."""
    import inspect
    from typing import get_type_hints

    # Check fetch method signature
    fetch_hints = get_type_hints(BaseFetcher.fetch)
    assert fetch_hints["return"] == FetchResult

    # Check test_connection signature
    connection_hints = get_type_hints(BaseFetcher.test_connection)
    assert connection_hints["return"] == bool

    # Check get_capabilities signature
    capabilities_hints = get_type_hints(BaseFetcher.get_capabilities)
    assert capabilities_hints["return"] == Dict[str, Any]
