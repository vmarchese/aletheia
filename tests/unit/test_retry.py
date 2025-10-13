"""Unit tests for retry logic."""

import time
from unittest.mock import MagicMock

import pytest

from aletheia.utils.retry import retry_with_backoff


class CustomError(Exception):
    """Custom exception for testing."""

    pass


class AnotherError(Exception):
    """Another custom exception for testing."""

    pass


def test_retry_success_on_first_attempt():
    """Test that successful function executes without retry."""
    mock_func = MagicMock(return_value="success")
    decorated = retry_with_backoff()(mock_func)

    result = decorated()

    assert result == "success"
    assert mock_func.call_count == 1


def test_retry_success_on_second_attempt():
    """Test that function succeeds on retry after initial failure."""
    mock_func = MagicMock(side_effect=[CustomError("fail"), "success"])
    decorated = retry_with_backoff(retries=2)(mock_func)

    result = decorated()

    assert result == "success"
    assert mock_func.call_count == 2


def test_retry_success_on_last_attempt():
    """Test that function succeeds on the last retry attempt."""
    mock_func = MagicMock(
        side_effect=[CustomError("fail1"), CustomError("fail2"), "success"]
    )
    decorated = retry_with_backoff(retries=3)(mock_func)

    result = decorated()

    assert result == "success"
    assert mock_func.call_count == 3


def test_retry_exhausted_raises_exception():
    """Test that exception is raised after all retries are exhausted."""
    mock_func = MagicMock(side_effect=CustomError("persistent failure"))
    decorated = retry_with_backoff(retries=3)(mock_func)

    with pytest.raises(CustomError, match="persistent failure"):
        decorated()

    assert mock_func.call_count == 4  # 1 initial + 3 retries


def test_retry_default_delays():
    """Test default exponential backoff delays (1s, 2s, 4s)."""
    mock_func = MagicMock(side_effect=CustomError("fail"))
    decorated = retry_with_backoff(retries=3)(mock_func)

    start_time = time.time()
    with pytest.raises(CustomError):
        decorated()
    elapsed = time.time() - start_time

    # Should have delays of 1s + 2s + 4s = 7s (approximately)
    assert elapsed >= 6.5  # Allow some tolerance
    assert elapsed < 8.0
    assert mock_func.call_count == 4


def test_retry_custom_delays():
    """Test custom retry delays."""
    mock_func = MagicMock(side_effect=CustomError("fail"))
    decorated = retry_with_backoff(retries=2, delays=(0.1, 0.2))(mock_func)

    start_time = time.time()
    with pytest.raises(CustomError):
        decorated()
    elapsed = time.time() - start_time

    # Should have delays of 0.1s + 0.2s = 0.3s (approximately)
    assert elapsed >= 0.25  # Allow some tolerance
    assert elapsed < 0.5
    assert mock_func.call_count == 3  # 1 initial + 2 retries


def test_retry_insufficient_delays_padding():
    """Test that insufficient delays are padded with last value."""
    mock_func = MagicMock(side_effect=CustomError("fail"))
    decorated = retry_with_backoff(retries=3, delays=(0.1,))(mock_func)

    start_time = time.time()
    with pytest.raises(CustomError):
        decorated()
    elapsed = time.time() - start_time

    # Should pad to (0.1, 0.1, 0.1) = 0.3s total
    assert elapsed >= 0.25
    assert elapsed < 0.5
    assert mock_func.call_count == 4


def test_retry_specific_exceptions_only():
    """Test that only specified exceptions trigger retry."""
    mock_func = MagicMock(side_effect=CustomError("fail"))
    decorated = retry_with_backoff(retries=3, exceptions=(CustomError,))(mock_func)

    with pytest.raises(CustomError):
        decorated()

    assert mock_func.call_count == 4  # Retries CustomError


def test_retry_unspecified_exception_no_retry():
    """Test that unspecified exceptions are not retried."""
    mock_func = MagicMock(side_effect=AnotherError("different error"))
    decorated = retry_with_backoff(retries=3, exceptions=(CustomError,))(mock_func)

    with pytest.raises(AnotherError, match="different error"):
        decorated()

    assert mock_func.call_count == 1  # No retry for AnotherError


def test_retry_multiple_exception_types():
    """Test retry with multiple exception types."""
    mock_func = MagicMock(
        side_effect=[CustomError("fail1"), AnotherError("fail2"), "success"]
    )
    decorated = retry_with_backoff(
        retries=3, delays=(0.1, 0.1, 0.1), exceptions=(CustomError, AnotherError)
    )(mock_func)

    result = decorated()

    assert result == "success"
    assert mock_func.call_count == 3


def test_retry_with_args_and_kwargs():
    """Test that function arguments are preserved through retries."""
    mock_func = MagicMock(side_effect=[CustomError("fail"), "success"])
    decorated = retry_with_backoff(retries=2, delays=(0.1, 0.1))(mock_func)

    result = decorated("arg1", "arg2", kwarg1="value1", kwarg2="value2")

    assert result == "success"
    assert mock_func.call_count == 2
    mock_func.assert_called_with("arg1", "arg2", kwarg1="value1", kwarg2="value2")


def test_retry_preserves_function_metadata():
    """Test that decorator preserves function name and docstring."""

    @retry_with_backoff(retries=3)
    def example_function():
        """Example docstring."""
        return "result"

    assert example_function.__name__ == "example_function"
    assert example_function.__doc__ == "Example docstring."


def test_retry_zero_retries():
    """Test that zero retries means only one attempt."""
    mock_func = MagicMock(side_effect=CustomError("fail"))
    decorated = retry_with_backoff(retries=0)(mock_func)

    with pytest.raises(CustomError):
        decorated()

    assert mock_func.call_count == 1  # Only initial attempt, no retries


def test_retry_single_retry():
    """Test single retry configuration."""
    mock_func = MagicMock(side_effect=[CustomError("fail"), "success"])
    decorated = retry_with_backoff(retries=1, delays=(0.1,))(mock_func)

    result = decorated()

    assert result == "success"
    assert mock_func.call_count == 2  # 1 initial + 1 retry


def test_retry_connection_timeout_scenario():
    """Test realistic scenario: connection timeout with retries."""

    class ConnectionTimeout(Exception):
        pass

    @retry_with_backoff(retries=3, delays=(0.1, 0.2, 0.4), exceptions=(ConnectionTimeout,))
    def fetch_data():
        # Simulates intermittent connection issues
        if fetch_data.attempt < 2:
            fetch_data.attempt += 1
            raise ConnectionTimeout("Connection timed out")
        return {"data": "success"}

    fetch_data.attempt = 0

    result = fetch_data()

    assert result == {"data": "success"}
    assert fetch_data.attempt == 2


def test_retry_no_delay_on_last_failure():
    """Test that no delay occurs after the last failed attempt."""
    mock_func = MagicMock(side_effect=CustomError("fail"))
    decorated = retry_with_backoff(retries=2, delays=(0.1, 0.2))(mock_func)

    start_time = time.time()
    with pytest.raises(CustomError):
        decorated()
    elapsed = time.time() - start_time

    # Should have delays only between attempts: 0.1 + 0.2 = 0.3s
    # No delay after the last failed attempt
    assert elapsed >= 0.25
    assert elapsed < 0.5


def test_retry_exception_message_preserved():
    """Test that original exception message is preserved."""
    expected_message = "specific error details: 404 not found"
    mock_func = MagicMock(side_effect=CustomError(expected_message))
    decorated = retry_with_backoff(retries=2, delays=(0.01, 0.01))(mock_func)

    with pytest.raises(CustomError, match=expected_message):
        decorated()
