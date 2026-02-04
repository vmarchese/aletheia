from enum import Enum


class SessionDataType(Enum):
    """Types of session data."""

    LOGS = "logs"
    METRICS = "metrics"
    TRACES = "traces"
    INFO = "info"
    TCPDUMP = "tcpdump"
