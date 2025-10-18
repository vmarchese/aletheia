"""Unit tests for scratchpad module."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.encryption import create_session_encryption


@pytest.fixture
def temp_session_dir():
    """Create a temporary session directory."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def encryption_key():
    """Create an encryption key for testing."""
    key, _ = create_session_encryption("test-password-123")
    return key


@pytest.fixture
def scratchpad(temp_session_dir, encryption_key):
    """Create a scratchpad instance for testing."""
    return Scratchpad(temp_session_dir, encryption_key)


# Test Section: Basic Operations

def test_scratchpad_initialization(temp_session_dir, encryption_key):
    """Test scratchpad initialization."""
    scratchpad = Scratchpad(temp_session_dir, encryption_key)

    assert scratchpad.session_dir == temp_session_dir
    assert scratchpad.encryption_key == encryption_key
    assert scratchpad.section_count == 0
    assert scratchpad.updated_at is None


def test_write_section(scratchpad):
    """Test writing a section."""
    data = {
        "description": "API errors in payments",
        "time_window": "2h",
        "affected_services": ["payments-svc"]
    }

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, data)

    assert scratchpad.section_count == 1
    assert scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
    assert scratchpad.updated_at is not None


def test_read_section(scratchpad):
    """Test reading a section."""
    data = {"test": "data", "value": 123}
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, data)

    read_data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)

    assert read_data == data
    assert read_data["test"] == "data"
    assert read_data["value"] == 123


def test_read_nonexistent_section(scratchpad):
    """Test reading a section that doesn't exist."""
    result = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)

    assert result is None


def test_has_section(scratchpad):
    """Test checking if a section exists."""
    assert not scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})

    assert scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
    assert not scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)


def test_get_all(scratchpad):
    """Test getting all scratchpad data."""
    problem = {"description": "test problem"}
    data = {"logs": [{"source": "k8s"}]}

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, problem)
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, data)

    all_data = scratchpad.get_all()

    assert len(all_data) == 2
    assert all_data[ScratchpadSection.PROBLEM_DESCRIPTION] == problem
    assert all_data[ScratchpadSection.DATA_COLLECTED] == data


def test_get_all_returns_copy(scratchpad):
    """Test that get_all returns a copy, not the original data."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})

    all_data = scratchpad.get_all()
    all_data["NEW_SECTION"] = {"modified": True}

    # Original should not be modified
    assert not scratchpad.has_section("NEW_SECTION")
    assert scratchpad.section_count == 1


def test_clear(scratchpad):
    """Test clearing all scratchpad data."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {"logs": []})

    assert scratchpad.section_count == 2

    scratchpad.clear()

    assert scratchpad.section_count == 0
    assert not scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
    assert not scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)


# Test Section: Append Operations

def test_append_to_nonexistent_section(scratchpad):
    """Test appending to a section that doesn't exist creates it."""
    data = {"new": "data"}

    scratchpad.append_to_section(ScratchpadSection.DATA_COLLECTED, data)

    assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
    assert scratchpad.read_section(ScratchpadSection.DATA_COLLECTED) == data


def test_append_dict_to_dict(scratchpad):
    """Test appending dict to dict section updates it."""
    initial = {"key1": "value1"}
    append = {"key2": "value2"}

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, initial)
    scratchpad.append_to_section(ScratchpadSection.PROBLEM_DESCRIPTION, append)

    result = scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
    assert result["key1"] == "value1"
    assert result["key2"] == "value2"


def test_append_dict_to_list(scratchpad):
    """Test appending dict to list section adds to list."""
    initial = [{"item": 1}]
    append = {"item": 2}

    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, initial)
    scratchpad.append_to_section(ScratchpadSection.DATA_COLLECTED, append)

    result = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
    assert len(result) == 2
    assert result[0]["item"] == 1
    assert result[1]["item"] == 2


def test_append_list_to_list(scratchpad):
    """Test appending list to list section extends it."""
    initial = [1, 2]
    append = [3, 4]

    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, initial)
    scratchpad.append_to_section(ScratchpadSection.DATA_COLLECTED, append)

    result = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
    assert result == [1, 2, 3, 4]


def test_append_incompatible_types_replaces(scratchpad):
    """Test appending incompatible types replaces the section."""
    initial = "string data"
    append = {"new": "dict"}

    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, initial)
    scratchpad.append_to_section(ScratchpadSection.PATTERN_ANALYSIS, append)

    result = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)
    assert result == append


# Test Section: Save and Load

def test_save_creates_encrypted_file(scratchpad, temp_session_dir):
    """Test that save creates an encrypted file."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})

    saved_path = scratchpad.save()

    assert saved_path.exists()
    assert saved_path.name == "scratchpad.encrypted"
    assert saved_path.parent == temp_session_dir


def test_save_and_load_roundtrip(scratchpad, temp_session_dir, encryption_key):
    """Test that save and load preserve data."""
    problem = {
        "description": "Payment failures",
        "time_window": "2h",
        "affected_services": ["payments-svc", "checkout-svc"]
    }
    data_collected = {
        "logs": [
            {"source": "kubernetes", "count": 200},
            {"source": "elasticsearch", "count": 150}
        ],
        "metrics": [
            {"source": "prometheus", "summary": "Error rate spike"}
        ]
    }

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, problem)
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, data_collected)
    scratchpad.save()

    # Load in new instance
    loaded = Scratchpad.load(temp_session_dir, encryption_key)

    assert loaded.section_count == 2
    assert loaded.read_section(ScratchpadSection.PROBLEM_DESCRIPTION) == problem
    assert loaded.read_section(ScratchpadSection.DATA_COLLECTED) == data_collected


def test_load_preserves_updated_at(scratchpad, temp_session_dir, encryption_key):
    """Test that load preserves the updated_at timestamp."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})
    original_time = scratchpad.updated_at
    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)

    assert loaded.updated_at is not None
    # Timestamps should be very close (within 1 second)
    assert abs((loaded.updated_at - original_time).total_seconds()) < 1


def test_load_nonexistent_file_raises_error(temp_session_dir, encryption_key):
    """Test that loading a nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Scratchpad.load(temp_session_dir, encryption_key)


def test_load_with_wrong_key_raises_error(scratchpad, temp_session_dir):
    """Test that loading with wrong encryption key fails."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})
    scratchpad.save()

    # Create different key
    wrong_key, _ = create_session_encryption("wrong-password")

    with pytest.raises(Exception):  # DecryptionError or similar
        Scratchpad.load(temp_session_dir, wrong_key)


# Test Section: Serialization

def test_to_yaml(scratchpad):
    """Test YAML serialization."""
    data = {
        "description": "Test problem",
        "services": ["svc1", "svc2"]
    }
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, data)

    yaml_str = scratchpad.to_yaml()

    assert "PROBLEM_DESCRIPTION" in yaml_str
    assert "description: Test problem" in yaml_str
    assert "services:" in yaml_str


def test_to_dict(scratchpad):
    """Test dictionary serialization."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})

    result = scratchpad.to_dict()

    assert "sections" in result
    assert "updated_at" in result
    assert result["sections"][ScratchpadSection.PROBLEM_DESCRIPTION] == {"test": "data"}


def test_to_dict_with_no_updates(temp_session_dir, encryption_key):
    """Test to_dict with no updates shows None for updated_at."""
    scratchpad = Scratchpad(temp_session_dir, encryption_key)

    result = scratchpad.to_dict()

    assert result["updated_at"] is None
    assert result["sections"] == {}


# Test Section: Complex Data Structures

def test_complex_nested_data(scratchpad, temp_session_dir, encryption_key):
    """Test handling complex nested data structures."""
    complex_data = {
        "anomalies": [
            {
                "type": "error_rate_spike",
                "timestamp": "2025-10-13T08:05:00Z",
                "severity": "critical",
                "metrics": {
                    "before": 0.2,
                    "after": 7.3,
                    "increase_factor": 36.5
                }
            }
        ],
        "correlations": [
            {
                "type": "temporal_alignment",
                "events": ["deployment", "error_spike"],
                "confidence": 0.92
            }
        ],
        "timeline": [
            {"time": "08:05:14", "event": "First panic"},
            {"time": "08:05:15", "event": "Circuit breaker opens"}
        ]
    }

    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, complex_data)
    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)
    result = loaded.read_section(ScratchpadSection.PATTERN_ANALYSIS)

    assert result == complex_data
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["metrics"]["increase_factor"] == 36.5


def test_unicode_and_special_characters(scratchpad, temp_session_dir, encryption_key):
    """Test handling Unicode and special characters."""
    data = {
        "description": "Error: Système de paiement échoué 🚨",
        "stack_trace": "panic: runtime error\n\tat main.go:42\n\tat server.go:156",
        "symbols": "→ ⇒ ✅ ❌ ⚠️"
    }

    scratchpad.write_section(ScratchpadSection.CODE_INSPECTION, data)
    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)
    result = loaded.read_section(ScratchpadSection.CODE_INSPECTION)

    assert result == data
    assert "🚨" in result["description"]
    assert "✅" in result["symbols"]


def test_large_data_handling(scratchpad, temp_session_dir, encryption_key):
    """Test handling large data sets (>1MB)."""
    # Create large log collection
    large_logs = [
        {
            "timestamp": f"2025-10-13T08:05:{i:02d}Z",
            "level": "ERROR",
            "message": f"Error message number {i} with some context and stack trace data" * 10,
            "service": "payments-svc",
            "pod": f"payments-svc-{i % 10}"
        }
        for i in range(1000)
    ]

    data = {
        "logs": large_logs,
        "total_count": len(large_logs),
        "summary": "Large log collection for testing"
    }

    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, data)
    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)
    result = loaded.read_section(ScratchpadSection.DATA_COLLECTED)

    assert len(result["logs"]) == 1000
    assert result["total_count"] == 1000


# Test Section: All Standard Sections

def test_all_standard_sections(scratchpad, temp_session_dir, encryption_key):
    """Test writing and loading all standard scratchpad sections."""
    # Problem description
    problem = {
        "description": "Payment API 500 errors",
        "time_window": "2h",
        "affected_services": ["payments-svc"],
        "mode": "guided"
    }

    # Data collected
    data = {
        "logs": [{"source": "kubernetes", "count": 200}],
        "metrics": [{"source": "prometheus", "summary": "Error spike"}]
    }

    # Pattern analysis
    patterns = {
        "anomalies": [{"type": "error_rate_spike", "severity": "critical"}],
        "correlations": [{"type": "deployment_correlation", "confidence": 0.92}]
    }

    # Code inspection
    code = {
        "suspect_files": [
            {"file": "features.go", "line": 57, "function": "IsEnabled"}
        ],
        "git_blame": {"author": "john.doe", "commit": "a3f9c2d"}
    }

    # Final diagnosis
    diagnosis = {
        "root_cause": {
            "type": "nil_pointer_dereference",
            "confidence": 0.86,
            "description": "IsEnabled dereferences nil pointer"
        },
        "recommended_actions": [
            {"priority": "immediate", "action": "Rollback to v1.18"}
        ]
    }

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, problem)
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, data)
    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, patterns)
    scratchpad.write_section(ScratchpadSection.CODE_INSPECTION, code)
    scratchpad.write_section(ScratchpadSection.FINAL_DIAGNOSIS, diagnosis)

    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)

    assert loaded.section_count == 5
    assert loaded.read_section(ScratchpadSection.PROBLEM_DESCRIPTION) == problem
    assert loaded.read_section(ScratchpadSection.DATA_COLLECTED) == data
    assert loaded.read_section(ScratchpadSection.PATTERN_ANALYSIS) == patterns
    assert loaded.read_section(ScratchpadSection.CODE_INSPECTION) == code
    assert loaded.read_section(ScratchpadSection.FINAL_DIAGNOSIS) == diagnosis


# Test Section: Properties

def test_section_count_property(scratchpad):
    """Test section_count property."""
    assert scratchpad.section_count == 0

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {})
    assert scratchpad.section_count == 1

    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {})
    assert scratchpad.section_count == 2

    scratchpad.clear()
    assert scratchpad.section_count == 0


def test_updated_at_property(scratchpad):
    """Test updated_at property."""
    assert scratchpad.updated_at is None

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})

    assert scratchpad.updated_at is not None
    assert isinstance(scratchpad.updated_at, datetime)


def test_updated_at_updates_on_write(scratchpad):
    """Test that updated_at is updated on each write."""
    import time

    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"test": "data"})
    first_time = scratchpad.updated_at

    time.sleep(0.1)  # Small delay

    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {"more": "data"})
    second_time = scratchpad.updated_at

    assert second_time > first_time


# Test Section: Edge Cases

def test_empty_section_data(scratchpad):
    """Test writing empty data structures."""
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {})
    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, [])
    scratchpad.write_section(ScratchpadSection.CODE_INSPECTION, "")

    assert scratchpad.section_count == 3
    assert scratchpad.read_section(ScratchpadSection.DATA_COLLECTED) == {}
    assert scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS) == []
    assert scratchpad.read_section(ScratchpadSection.CODE_INSPECTION) == ""


def test_overwriting_section(scratchpad):
    """Test that writing to existing section overwrites it."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"old": "data"})
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"new": "data"})

    result = scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)

    assert result == {"new": "data"}
    assert "old" not in result


def test_none_values(scratchpad):
    """Test handling None values in data."""
    data = {
        "required_field": "value",
        "optional_field": None,
        "nested": {
            "also_optional": None
        }
    }

    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, data)
    result = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)

    assert result == data
    assert result["optional_field"] is None


# Test Section: Conversational Support (REFACTOR-6)

def test_append_conversation_creates_history(scratchpad):
    """Test that append_conversation creates CONVERSATION_HISTORY section."""
    scratchpad.append_conversation("user", "Why is my service failing?")

    assert scratchpad.has_section(ScratchpadSection.CONVERSATION_HISTORY)
    history = scratchpad.read_section(ScratchpadSection.CONVERSATION_HISTORY)

    assert isinstance(history, list)
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["message"] == "Why is my service failing?"
    assert "timestamp" in history[0]


def test_append_conversation_multiple_messages(scratchpad):
    """Test appending multiple conversation messages."""
    scratchpad.append_conversation("user", "Why is my service failing?")
    scratchpad.append_conversation("agent", "Let me collect data to investigate...")
    scratchpad.append_conversation("user", "It started 2 hours ago")

    history = scratchpad.read_section(ScratchpadSection.CONVERSATION_HISTORY)

    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "agent"
    assert history[2]["role"] == "user"
    assert history[2]["message"] == "It started 2 hours ago"


def test_append_conversation_preserves_order(scratchpad):
    """Test that conversation messages preserve chronological order."""
    messages = [
        ("user", "First message"),
        ("agent", "Second message"),
        ("system", "Third message"),
        ("user", "Fourth message")
    ]

    for role, message in messages:
        scratchpad.append_conversation(role, message)

    history = scratchpad.read_section(ScratchpadSection.CONVERSATION_HISTORY)

    assert len(history) == 4
    for i, (role, message) in enumerate(messages):
        assert history[i]["role"] == role
        assert history[i]["message"] == message


def test_append_conversation_includes_timestamp(scratchpad):
    """Test that append_conversation includes ISO format timestamp."""
    import time

    scratchpad.append_conversation("user", "First message")
    time.sleep(0.1)
    scratchpad.append_conversation("user", "Second message")

    history = scratchpad.read_section(ScratchpadSection.CONVERSATION_HISTORY)

    # Both messages should have timestamps
    assert "timestamp" in history[0]
    assert "timestamp" in history[1]

    # Parse timestamps to verify format
    from datetime import datetime
    ts1 = datetime.fromisoformat(history[0]["timestamp"])
    ts2 = datetime.fromisoformat(history[1]["timestamp"])

    # Second timestamp should be later
    assert ts2 > ts1


def test_get_conversation_context_empty(scratchpad):
    """Test get_conversation_context returns empty string when no history."""
    context = scratchpad.get_conversation_context()

    assert context == ""


def test_get_conversation_context_formats_messages(scratchpad):
    """Test get_conversation_context formats messages correctly."""
    scratchpad.append_conversation("user", "Why is my service failing?")
    scratchpad.append_conversation("agent", "Let me investigate...")

    context = scratchpad.get_conversation_context()

    assert "user: Why is my service failing?" in context
    assert "agent: Let me investigate..." in context
    assert context.count("\n") == 1  # Two messages, one newline


def test_get_conversation_context_multiline(scratchpad):
    """Test get_conversation_context handles multiline messages."""
    scratchpad.append_conversation("user", "Line 1\nLine 2\nLine 3")
    scratchpad.append_conversation("agent", "Response")

    context = scratchpad.get_conversation_context()

    # Multiline message should be preserved
    assert "Line 1\nLine 2\nLine 3" in context
    assert "agent: Response" in context


def test_conversation_persists_after_save_load(scratchpad, temp_session_dir, encryption_key):
    """Test that conversation history persists through save/load."""
    scratchpad.append_conversation("user", "First message")
    scratchpad.append_conversation("agent", "Second message")
    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)
    history = loaded.read_section(ScratchpadSection.CONVERSATION_HISTORY)

    assert len(history) == 2
    assert history[0]["message"] == "First message"
    assert history[1]["message"] == "Second message"


def test_conversation_context_after_load(scratchpad, temp_session_dir, encryption_key):
    """Test get_conversation_context works after load."""
    scratchpad.append_conversation("user", "Question")
    scratchpad.append_conversation("agent", "Answer")
    scratchpad.save()

    loaded = Scratchpad.load(temp_session_dir, encryption_key)
    context = loaded.get_conversation_context()

    assert "user: Question" in context
    assert "agent: Answer" in context


def test_agent_notes_section(scratchpad):
    """Test AGENT_NOTES section for conversational findings."""
    notes = {
        "data_fetcher": {
            "finding": "Collected 200 logs with 47 errors",
            "timestamp": "2025-10-18T10:00:00Z"
        },
        "pattern_analyzer": {
            "finding": "Detected error rate spike at 08:05",
            "timestamp": "2025-10-18T10:01:00Z"
        }
    }

    scratchpad.write_section(ScratchpadSection.AGENT_NOTES, notes)

    assert scratchpad.has_section(ScratchpadSection.AGENT_NOTES)
    result = scratchpad.read_section(ScratchpadSection.AGENT_NOTES)

    assert result == notes
    assert "data_fetcher" in result
    assert "pattern_analyzer" in result


def test_agent_notes_flexible_structure(scratchpad):
    """Test AGENT_NOTES supports flexible data structures."""
    # Different agents can use different formats
    scratchpad.write_section(ScratchpadSection.AGENT_NOTES, {})

    # Data fetcher uses list format
    scratchpad.append_to_section(ScratchpadSection.AGENT_NOTES, {
        "data_fetcher": ["Found 47 errors", "Collected from 3 pods"]
    })

    # Pattern analyzer uses dict format
    scratchpad.append_to_section(ScratchpadSection.AGENT_NOTES, {
        "pattern_analyzer": {
            "anomalies": 3,
            "confidence": 0.85
        }
    })

    result = scratchpad.read_section(ScratchpadSection.AGENT_NOTES)

    assert isinstance(result["data_fetcher"], list)
    assert isinstance(result["pattern_analyzer"], dict)
    assert len(result["data_fetcher"]) == 2
    assert result["pattern_analyzer"]["confidence"] == 0.85


def test_conversation_with_special_characters(scratchpad):
    """Test conversation handles special characters and emojis."""
    scratchpad.append_conversation("user", "Service is down 🚨")
    scratchpad.append_conversation("agent", "I'll investigate → checking logs")

    history = scratchpad.read_section(ScratchpadSection.CONVERSATION_HISTORY)
    context = scratchpad.get_conversation_context()

    assert "🚨" in history[0]["message"]
    assert "→" in history[1]["message"]
    assert "🚨" in context
    assert "→" in context


def test_conversation_roles_flexible(scratchpad):
    """Test that conversation supports various role names."""
    roles = ["user", "agent", "system", "orchestrator", "data_fetcher", "pattern_analyzer"]

    for role in roles:
        scratchpad.append_conversation(role, f"Message from {role}")

    history = scratchpad.read_section(ScratchpadSection.CONVERSATION_HISTORY)

    assert len(history) == len(roles)
    for i, role in enumerate(roles):
        assert history[i]["role"] == role

