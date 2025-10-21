"""Tests for session persistence utilities."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from aletheia.utils.session_persistence import (
    sanitize_filename,
    generate_timestamp,
    save_logs_to_session,
    save_metrics_to_session,
    save_traces_to_session,
)


def test_sanitize_filename_basic():
    """Test basic filename sanitization."""
    assert sanitize_filename("test-pod") == "test-pod"
    assert sanitize_filename("test_pod") == "test_pod"
    assert sanitize_filename("test pod") == "test_pod"
    assert sanitize_filename("test:pod") == "test_pod"
    assert sanitize_filename("test/pod") == "test_pod"


def test_sanitize_filename_special_chars():
    """Test filename sanitization with special characters."""
    assert sanitize_filename("test@pod#123") == "test_pod_123"
    assert sanitize_filename("test!pod$name") == "test_pod_name"
    assert sanitize_filename("test&pod*name") == "test_pod_name"


def test_sanitize_filename_consecutive_underscores():
    """Test removal of consecutive underscores."""
    assert sanitize_filename("test___pod") == "test_pod"
    assert sanitize_filename("test  pod  name") == "test_pod_name"


def test_sanitize_filename_max_length():
    """Test filename length truncation."""
    long_name = "a" * 100
    result = sanitize_filename(long_name, max_length=50)
    assert len(result) == 50
    assert result == "a" * 50


def test_sanitize_filename_empty():
    """Test sanitization of empty or invalid strings."""
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("___") == "unnamed"
    assert sanitize_filename("   ") == "unnamed"


def test_generate_timestamp():
    """Test timestamp generation."""
    timestamp = generate_timestamp()
    assert len(timestamp) == 19  # YYYY-MM-DDTHH-MM-SS
    assert timestamp.count("-") == 4  # Date has 2, time has 2
    assert "T" in timestamp
    
    # Should be valid datetime when we reverse the replacement
    datetime_str = timestamp.replace("T", " ").replace("-", ":", 2)
    # Not perfect but validates basic structure


def test_save_logs_to_session(tmp_path):
    """Test saving logs to session folder."""
    logs = [
        {"timestamp": "2025-10-21T10:00:00", "level": "ERROR", "message": "Test error 1"},
        {"timestamp": "2025-10-21T10:00:01", "level": "ERROR", "message": "Test error 2"},
    ]
    metadata = {
        "pod": "test-pod",
        "namespace": "default",
        "time_range": ["2025-10-21T10:00:00", "2025-10-21T11:00:00"],
    }
    
    file_path = save_logs_to_session(
        tmp_path,
        logs,
        metadata,
        source="kubernetes",
        identifier="test-pod",
    )
    
    # Verify file was created
    assert file_path.exists()
    assert file_path.parent == tmp_path / "logs"
    assert file_path.name.startswith("kubernetes_test-pod_")
    assert file_path.suffix == ".json"
    
    # Verify file content
    with open(file_path, "r") as f:
        data = json.load(f)
    
    assert data["source"] == "kubernetes"
    assert data["data"] == logs
    assert data["metadata"]["pod"] == "test-pod"
    assert data["metadata"]["namespace"] == "default"
    assert data["metadata"]["count"] == 2
    assert "collected_at" in data["metadata"]


def test_save_logs_to_session_without_identifier(tmp_path):
    """Test saving logs without an identifier."""
    logs = [{"timestamp": "2025-10-21T10:00:00", "level": "INFO", "message": "Test"}]
    metadata = {}
    
    file_path = save_logs_to_session(
        tmp_path,
        logs,
        metadata,
        source="kubernetes",
    )
    
    assert file_path.exists()
    assert file_path.name.startswith("kubernetes_")
    assert "unknown" not in file_path.name  # No identifier, so no "unknown"


def test_save_metrics_to_session(tmp_path):
    """Test saving metrics to session folder."""
    metrics = [
        {"timestamp": 1698064800, "value": 0.5},
        {"timestamp": 1698064860, "value": 0.7},
    ]
    metadata = {
        "query": "rate(http_requests_total[5m])",
        "time_range": ["2025-10-21T10:00:00", "2025-10-21T11:00:00"],
    }
    
    file_path = save_metrics_to_session(
        tmp_path,
        metrics,
        metadata,
        source="prometheus",
        query="rate(http_requests_total[5m])",
    )
    
    # Verify file was created
    assert file_path.exists()
    assert file_path.parent == tmp_path / "metrics"
    assert file_path.name.startswith("prometheus_rate_http_requests_total_5m_")
    assert file_path.suffix == ".json"
    
    # Verify file content
    with open(file_path, "r") as f:
        data = json.load(f)
    
    assert data["source"] == "prometheus"
    assert data["data"] == metrics
    assert data["metadata"]["query"] == "rate(http_requests_total[5m])"
    assert data["metadata"]["count"] == 2
    assert "collected_at" in data["metadata"]


def test_save_metrics_to_session_query_sanitization(tmp_path):
    """Test query string sanitization in filename."""
    metrics = [{"timestamp": 1698064800, "value": 1.0}]
    metadata = {"query": "rate(http_requests{job=\"api\"}[5m])"}
    
    file_path = save_metrics_to_session(
        tmp_path,
        metrics,
        metadata,
        source="prometheus",
        query='rate(http_requests{job="api"}[5m])',
    )
    
    assert file_path.exists()
    # Verify special characters are sanitized
    assert "{" not in file_path.name
    assert "}" not in file_path.name
    assert '"' not in file_path.name


def test_save_traces_to_session(tmp_path):
    """Test saving traces to session folder."""
    traces = [
        {"trace_id": "abc123", "span_id": "span1", "operation": "http.request"},
        {"trace_id": "abc123", "span_id": "span2", "operation": "db.query"},
    ]
    metadata = {
        "service": "payments-svc",
        "time_range": ["2025-10-21T10:00:00", "2025-10-21T11:00:00"],
    }
    
    file_path = save_traces_to_session(
        tmp_path,
        traces,
        metadata,
        source="jaeger",
        identifier="payments-svc",
    )
    
    # Verify file was created
    assert file_path.exists()
    assert file_path.parent == tmp_path / "traces"
    assert file_path.name.startswith("jaeger_payments-svc_")
    assert file_path.suffix == ".json"
    
    # Verify file content
    with open(file_path, "r") as f:
        data = json.load(f)
    
    assert data["source"] == "jaeger"
    assert data["data"] == traces
    assert data["metadata"]["service"] == "payments-svc"
    assert data["metadata"]["count"] == 2


def test_save_logs_creates_directory(tmp_path):
    """Test that save functions create necessary directories."""
    # Start with empty directory
    logs = [{"message": "test"}]
    
    file_path = save_logs_to_session(tmp_path, logs, {}, source="kubernetes")
    
    # Verify logs directory was created
    assert (tmp_path / "logs").exists()
    assert file_path.exists()


def test_save_metrics_creates_directory(tmp_path):
    """Test that metrics save creates necessary directories."""
    metrics = [{"value": 1.0}]
    
    file_path = save_metrics_to_session(tmp_path, metrics, {}, source="prometheus")
    
    # Verify metrics directory was created
    assert (tmp_path / "metrics").exists()
    assert file_path.exists()


def test_save_traces_creates_directory(tmp_path):
    """Test that traces save creates necessary directories."""
    traces = [{"span_id": "123"}]
    
    file_path = save_traces_to_session(tmp_path, traces, {}, source="jaeger")
    
    # Verify traces directory was created
    assert (tmp_path / "traces").exists()
    assert file_path.exists()


def test_save_logs_overwrites_existing_directory(tmp_path):
    """Test that save works when directory already exists."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    
    logs = [{"message": "test"}]
    file_path = save_logs_to_session(tmp_path, logs, {}, source="kubernetes")
    
    assert file_path.exists()


def test_save_logs_with_empty_data(tmp_path):
    """Test saving empty log list."""
    logs = []
    metadata = {"pod": "test"}
    
    file_path = save_logs_to_session(tmp_path, logs, metadata, source="kubernetes")
    
    assert file_path.exists()
    with open(file_path, "r") as f:
        data = json.load(f)
    
    assert data["data"] == []
    assert data["metadata"]["count"] == 0


def test_save_logs_unicode_handling(tmp_path):
    """Test saving logs with unicode characters."""
    logs = [
        {"message": "Error: データベース接続失敗"},
        {"message": "Erreur: échec de connexion"},
    ]
    metadata = {"pod": "test-pod"}
    
    file_path = save_logs_to_session(tmp_path, logs, metadata, source="kubernetes")
    
    assert file_path.exists()
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert data["data"][0]["message"] == "Error: データベース接続失敗"
    assert data["data"][1]["message"] == "Erreur: échec de connexion"


def test_save_logs_large_dataset(tmp_path):
    """Test saving a large number of logs."""
    logs = [{"index": i, "message": f"Log entry {i}"} for i in range(1000)]
    metadata = {"pod": "test-pod"}
    
    file_path = save_logs_to_session(tmp_path, logs, metadata, source="kubernetes")
    
    assert file_path.exists()
    with open(file_path, "r") as f:
        data = json.load(f)
    
    assert len(data["data"]) == 1000
    assert data["metadata"]["count"] == 1000
