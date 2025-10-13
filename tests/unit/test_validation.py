"""Unit tests for validation utilities."""

from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from aletheia.utils.validation import (
    ValidationError,
    validate_commit_hash,
    validate_git_repository,
    validate_service_name,
    validate_time_window,
)


# ========================================
# Tests for validate_git_repository
# ========================================


def test_validate_git_repository_valid(tmp_path):
    """Test validation of a valid git repository."""
    # Create a mock git repository
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    result = validate_git_repository(str(tmp_path))

    assert isinstance(result, Path)
    assert result == tmp_path


def test_validate_git_repository_with_tilde(tmp_path, monkeypatch):
    """Test that tilde expansion works."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Mock home directory
    monkeypatch.setenv("HOME", str(tmp_path.parent))

    # Use tilde path
    tilde_path = f"~/{tmp_path.name}"
    result = validate_git_repository(tilde_path)

    assert result == tmp_path


def test_validate_git_repository_nonexistent():
    """Test that nonexistent path raises ValidationError."""
    with pytest.raises(ValidationError, match="Path does not exist"):
        validate_git_repository("/nonexistent/path/to/repo")


def test_validate_git_repository_not_a_directory(tmp_path):
    """Test that a file path raises ValidationError."""
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("content")

    with pytest.raises(ValidationError, match="Path is not a directory"):
        validate_git_repository(str(file_path))


def test_validate_git_repository_missing_git_dir(tmp_path):
    """Test that directory without .git raises ValidationError."""
    with pytest.raises(ValidationError, match="Path is not a git repository"):
        validate_git_repository(str(tmp_path))


def test_validate_git_repository_relative_path(tmp_path):
    """Test that relative paths are resolved correctly."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # Change to parent directory and use relative path
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path.parent)
        result = validate_git_repository(tmp_path.name)
        assert result == tmp_path
    finally:
        os.chdir(original_cwd)


# ========================================
# Tests for validate_time_window
# ========================================


def test_validate_time_window_minutes():
    """Test parsing minutes format."""
    result = validate_time_window("30m")
    assert result == timedelta(minutes=30)


def test_validate_time_window_hours():
    """Test parsing hours format."""
    result = validate_time_window("2h")
    assert result == timedelta(hours=2)


def test_validate_time_window_days():
    """Test parsing days format."""
    result = validate_time_window("7d")
    assert result == timedelta(days=7)


def test_validate_time_window_weeks():
    """Test parsing weeks format."""
    result = validate_time_window("2w")
    assert result == timedelta(weeks=2)


def test_validate_time_window_case_insensitive():
    """Test that units are case-insensitive."""
    assert validate_time_window("30M") == timedelta(minutes=30)
    assert validate_time_window("2H") == timedelta(hours=2)
    assert validate_time_window("7D") == timedelta(days=7)
    assert validate_time_window("1W") == timedelta(weeks=1)


def test_validate_time_window_single_digit():
    """Test single-digit amounts."""
    assert validate_time_window("1m") == timedelta(minutes=1)
    assert validate_time_window("5h") == timedelta(hours=5)


def test_validate_time_window_large_numbers():
    """Test large valid numbers."""
    assert validate_time_window("120m") == timedelta(minutes=120)
    assert validate_time_window("48h") == timedelta(hours=48)


def test_validate_time_window_invalid_format_no_unit():
    """Test that number without unit raises error."""
    with pytest.raises(ValidationError, match="Invalid time window format"):
        validate_time_window("30")


def test_validate_time_window_invalid_format_no_number():
    """Test that unit without number raises error."""
    with pytest.raises(ValidationError, match="Invalid time window format"):
        validate_time_window("h")


def test_validate_time_window_invalid_unit():
    """Test that invalid unit raises error."""
    with pytest.raises(ValidationError, match="Invalid time window format"):
        validate_time_window("30s")  # seconds not supported


def test_validate_time_window_zero_amount():
    """Test that zero amount raises error."""
    with pytest.raises(ValidationError, match="Time window amount must be positive"):
        validate_time_window("0h")


def test_validate_time_window_negative_amount():
    """Test that negative amount raises error."""
    with pytest.raises(ValidationError, match="Invalid time window format"):
        validate_time_window("-2h")  # Negative not matched by regex


def test_validate_time_window_too_large():
    """Test that excessively large windows are rejected."""
    with pytest.raises(ValidationError, match="Time window too large"):
        validate_time_window("400d")  # More than 365 days


def test_validate_time_window_max_allowed():
    """Test that maximum allowed window (365 days) is accepted."""
    result = validate_time_window("365d")
    assert result == timedelta(days=365)


def test_validate_time_window_decimal_not_supported():
    """Test that decimal numbers are not supported."""
    with pytest.raises(ValidationError, match="Invalid time window format"):
        validate_time_window("2.5h")


def test_validate_time_window_whitespace():
    """Test that whitespace in input is not accepted."""
    with pytest.raises(ValidationError, match="Invalid time window format"):
        validate_time_window("30 m")


# ========================================
# Tests for validate_service_name
# ========================================


def test_validate_service_name_valid_simple():
    """Test simple valid service names."""
    assert validate_service_name("payments") == "payments"
    assert validate_service_name("api") == "api"


def test_validate_service_name_valid_with_hyphens():
    """Test valid service names with hyphens."""
    assert validate_service_name("payments-svc") == "payments-svc"
    assert validate_service_name("auth-service") == "auth-service"
    assert validate_service_name("my-app-123") == "my-app-123"


def test_validate_service_name_valid_with_numbers():
    """Test valid service names with numbers."""
    assert validate_service_name("app123") == "app123"
    assert validate_service_name("service-v2") == "service-v2"
    assert validate_service_name("1234") == "1234"


def test_validate_service_name_uppercase_normalized():
    """Test that uppercase is normalized to lowercase."""
    assert validate_service_name("PaymentsSvc") == "paymentssvc"
    assert validate_service_name("AUTH-SERVICE") == "auth-service"


def test_validate_service_name_empty_string():
    """Test that empty string raises error."""
    with pytest.raises(ValidationError, match="Service name cannot be empty"):
        validate_service_name("")


def test_validate_service_name_starts_with_hyphen():
    """Test that names starting with hyphen are rejected."""
    with pytest.raises(ValidationError, match="Invalid service name format"):
        validate_service_name("-payments")


def test_validate_service_name_ends_with_hyphen():
    """Test that names ending with hyphen are rejected."""
    with pytest.raises(ValidationError, match="Invalid service name format"):
        validate_service_name("payments-")


def test_validate_service_name_consecutive_hyphens():
    """Test that consecutive hyphens are allowed."""
    # Kubernetes allows this
    assert validate_service_name("my--service") == "my--service"


def test_validate_service_name_special_characters():
    """Test that special characters are rejected."""
    with pytest.raises(ValidationError, match="Invalid service name format"):
        validate_service_name("payments_svc")  # underscore not allowed

    with pytest.raises(ValidationError, match="Invalid service name format"):
        validate_service_name("payments.svc")  # dot not allowed

    with pytest.raises(ValidationError, match="Invalid service name format"):
        validate_service_name("payments svc")  # space not allowed


def test_validate_service_name_too_long():
    """Test that names exceeding 253 characters are rejected."""
    long_name = "a" * 254
    with pytest.raises(ValidationError, match="Service name too long"):
        validate_service_name(long_name)


def test_validate_service_name_max_length():
    """Test that names at exactly 253 characters are accepted."""
    max_name = "a" * 253
    assert validate_service_name(max_name) == max_name


def test_validate_service_name_single_character():
    """Test single-character names."""
    assert validate_service_name("a") == "a"
    assert validate_service_name("1") == "1"


# ========================================
# Tests for validate_commit_hash
# ========================================


def test_validate_commit_hash_short_valid():
    """Test valid 7-character short hash."""
    assert validate_commit_hash("a3f9c2d") == "a3f9c2d"


def test_validate_commit_hash_short_longer():
    """Test valid longer short hash (8-10 characters)."""
    assert validate_commit_hash("a3f9c2d8") == "a3f9c2d8"
    assert validate_commit_hash("a3f9c2d8f1") == "a3f9c2d8f1"


def test_validate_commit_hash_full_sha1():
    """Test valid full 40-character SHA-1 hash."""
    full_hash = "a3f9c2d8f1e2b4c6d8f9e1a2b3c4d5e6f7a8b9c0"
    assert validate_commit_hash(full_hash) == full_hash


def test_validate_commit_hash_uppercase_normalized():
    """Test that uppercase is normalized to lowercase."""
    assert validate_commit_hash("A3F9C2D") == "a3f9c2d"
    assert validate_commit_hash("A3F9C2D8F1E2B4C6D8F9E1A2B3C4D5E6F7A8B9C0") == (
        "a3f9c2d8f1e2b4c6d8f9e1a2b3c4d5e6f7a8b9c0"
    )


def test_validate_commit_hash_empty_string():
    """Test that empty string raises error."""
    with pytest.raises(ValidationError, match="Commit hash cannot be empty"):
        validate_commit_hash("")


def test_validate_commit_hash_invalid_characters():
    """Test that non-hex characters are rejected."""
    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash("g123456")  # 'g' is not hex

    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash("a3f9c2z")  # 'z' is not hex

    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash("a3f-9c2d")  # hyphen not allowed


def test_validate_commit_hash_too_short():
    """Test that hashes shorter than 7 characters are rejected."""
    with pytest.raises(ValidationError, match="Invalid commit hash length"):
        validate_commit_hash("a3f9c2")  # 6 characters


def test_validate_commit_hash_too_long():
    """Test that hashes longer than 40 characters are rejected."""
    too_long = "a" * 41
    with pytest.raises(ValidationError, match="Commit hash too long"):
        validate_commit_hash(too_long)


def test_validate_commit_hash_disallow_short():
    """Test that short hashes can be disallowed."""
    with pytest.raises(ValidationError, match="Expected 40 characters"):
        validate_commit_hash("a3f9c2d", allow_short=False)


def test_validate_commit_hash_require_full_sha1():
    """Test requiring full SHA-1 only."""
    full_hash = "a3f9c2d8f1e2b4c6d8f9e1a2b3c4d5e6f7a8b9c0"
    assert validate_commit_hash(full_hash, allow_short=False) == full_hash


def test_validate_commit_hash_whitespace():
    """Test that whitespace is not allowed."""
    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash("a3f9c2d ")  # trailing space

    with pytest.raises(ValidationError, match="Invalid commit hash format"):
        validate_commit_hash(" a3f9c2d")  # leading space


def test_validate_commit_hash_all_zeros():
    """Test that all-zero hashes are technically valid format."""
    # Git does use 0000000 for special cases
    assert validate_commit_hash("0000000") == "0000000"
    assert (
        validate_commit_hash("0000000000000000000000000000000000000000")
        == "0000000000000000000000000000000000000000"
    )


def test_validate_commit_hash_all_fs():
    """Test that all-F hashes are valid format."""
    assert validate_commit_hash("fffffff") == "fffffff"
    assert (
        validate_commit_hash("ffffffffffffffffffffffffffffffffffffffff")
        == "ffffffffffffffffffffffffffffffffffffffff"
    )


def test_validate_commit_hash_min_short_length():
    """Test minimum short hash length (7 characters)."""
    assert validate_commit_hash("1234567") == "1234567"


def test_validate_commit_hash_boundary_lengths():
    """Test various boundary lengths between short and full."""
    # 7 to 40 should all be valid
    for length in [7, 8, 10, 15, 20, 30, 39, 40]:
        hash_str = "a" * length
        assert validate_commit_hash(hash_str) == hash_str
