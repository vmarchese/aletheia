"""Validation utilities for user inputs and system state."""

import re
from datetime import timedelta
from pathlib import Path


class ValidationError(Exception):
    """Raised when validation fails."""


def validate_git_repository(path: str) -> Path:
    """
    Validate that a path is a git repository.

    Args:
        path: Path to check

    Returns:
        Validated Path object

    Raises:
        ValidationError: If path doesn't exist, is not a directory, or is not a git repo

    Example:
        >>> repo_path = validate_git_repository("/path/to/repo")
        >>> print(repo_path)
        /path/to/repo
    """
    repo_path = Path(path).expanduser().resolve()

    if not repo_path.exists():
        raise ValidationError(f"Path does not exist: {path}")

    if not repo_path.is_dir():
        raise ValidationError(f"Path is not a directory: {path}")

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        raise ValidationError(f"Path is not a git repository: {path}")

    return repo_path


def validate_time_window(window: str) -> timedelta:
    """
    Parse and validate a time window string.

    Supported formats:
    - "30m", "2h", "1d", "1w" (minutes, hours, days, weeks)
    - "HH:MM-HH:MM" (time range today)
    - ISO timestamps (future enhancement)

    Args:
        window: Time window string

    Returns:
        timedelta object representing the window

    Raises:
        ValidationError: If format is invalid or duration is invalid

    Example:
        >>> delta = validate_time_window("2h")
        >>> print(delta.total_seconds())
        7200.0

        >>> delta = validate_time_window("30m")
        >>> print(delta.total_seconds())
        1800.0
    """
    # Pattern: number followed by unit (m, h, d, w)
    pattern = r"^(\d+)(m|h|d|w)$"
    match = re.match(pattern, window.lower())

    if not match:
        raise ValidationError(
            f"Invalid time window format: {window}. "
            f"Expected format: '<number><unit>' where unit is m (minutes), "
            f"h (hours), d (days), or w (weeks). Examples: 30m, 2h, 1d"
        )

    amount, unit = match.groups()
    amount = int(amount)

    if amount <= 0:
        raise ValidationError(f"Time window amount must be positive: {amount}")

    # Convert to timedelta
    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    elif unit == "d":
        delta = timedelta(days=amount)
    elif unit == "w":
        delta = timedelta(weeks=amount)
    else:
        # This should never happen due to regex, but for safety
        raise ValidationError(f"Unknown time unit: {unit}")

    # Validate reasonable limits (e.g., not more than 1 year)
    max_days = 365
    if delta > timedelta(days=max_days):
        raise ValidationError(
            f"Time window too large: {window} ({delta.days} days). "
            f"Maximum allowed: {max_days} days"
        )

    return delta


def validate_service_name(name: str) -> str:
    """
    Validate a service name format.

    Service names should follow Kubernetes naming conventions:
    - Lowercase alphanumeric characters or '-'
    - Must start and end with alphanumeric character
    - Maximum 253 characters

    Args:
        name: Service name to validate

    Returns:
        Validated service name (lowercase)

    Raises:
        ValidationError: If name format is invalid

    Example:
        >>> validate_service_name("payments-svc")
        'payments-svc'

        >>> validate_service_name("PaymentsService")
        'paymentsservice'
    """
    if not name:
        raise ValidationError("Service name cannot be empty")

    # Normalize to lowercase
    normalized = name.lower()

    # Check length
    if len(normalized) > 253:
        raise ValidationError(
            f"Service name too long: {len(normalized)} characters. "
            f"Maximum allowed: 253 characters"
        )

    # Check format: alphanumeric or '-', must start/end with alphanumeric
    pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
    if not re.match(pattern, normalized):
        raise ValidationError(
            f"Invalid service name format: {name}. "
            f"Must contain only lowercase alphanumeric characters or '-', "
            f"and must start and end with an alphanumeric character."
        )

    return normalized


def validate_commit_hash(commit: str, allow_short: bool = True) -> str:
    """
    Validate a git commit hash format.

    Args:
        commit: Commit hash to validate (short or full)
        allow_short: Allow short (7-char) commit hashes (default: True)

    Returns:
        Validated commit hash (lowercase)

    Raises:
        ValidationError: If commit hash format is invalid

    Example:
        >>> validate_commit_hash("a3f9c2d")
        'a3f9c2d'

        >>> validate_commit_hash("a3f9c2d8f1e2b4c6d8f9e1a2b3c4d5e6f7a8b9c0")
        'a3f9c2d8f1e2b4c6d8f9e1a2b3c4d5e6f7a8b9c0'
    """
    if not commit:
        raise ValidationError("Commit hash cannot be empty")

    # Normalize to lowercase
    normalized = commit.lower()

    # Check if it's a valid hex string
    if not re.match(r"^[0-9a-f]+$", normalized):
        raise ValidationError(
            f"Invalid commit hash format: {commit}. "
            f"Must contain only hexadecimal characters (0-9, a-f)."
        )

    # Check length: 7 chars (short) or 40 chars (full SHA-1)
    if len(normalized) == 40:
        # Full SHA-1 hash
        return normalized
    elif len(normalized) >= 7 and allow_short:
        # Short hash (at least 7 chars, but can be longer for safety)
        if len(normalized) > 40:
            raise ValidationError(
                f"Commit hash too long: {len(normalized)} characters. "
                f"Maximum allowed: 40 characters (SHA-1)"
            )
        return normalized
    else:
        if allow_short:
            raise ValidationError(
                f"Invalid commit hash length: {len(normalized)} characters. "
                f"Expected 7+ characters (short hash) or 40 characters (full SHA-1)."
            )
        else:
            raise ValidationError(
                f"Invalid commit hash length: {len(normalized)} characters. "
                f"Expected 40 characters (full SHA-1). Short hashes not allowed."
            )
