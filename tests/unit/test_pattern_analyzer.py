"""Unit tests for Pattern Analyzer Agent."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.scratchpad import Scratchpad, ScratchpadSection


class TestPatternAnalyzerInitialization:
    """Test Pattern Analyzer Agent initialization."""
    
    def test_initialization(self):
        """Test basic initialization."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        assert agent.agent_name == "pattern_analyzer"
        assert agent.config == config
        assert agent.scratchpad == scratchpad


class TestMetricAnomalyDetection:
    """Test metric anomaly detection."""
    
    def test_identify_metric_spike(self):
        """Test identifying metric spike anomaly."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "prometheus": {
                "source": "prometheus",
                "count": 120,
                "summary": "spike detected: 7.30 (avg: 0.85) at 2025-10-14T10:05:00",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_metric_anomalies(collected_data)
        
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "metric_spike"
        assert anomalies[0]["severity"] == "critical"
        assert "7.30" in anomalies[0]["description"]
    
    def test_identify_metric_drop(self):
        """Test identifying metric drop anomaly."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "prometheus": {
                "source": "prometheus",
                "count": 120,
                "summary": "drop detected: 0.05 (avg: 2.50) at 2025-10-14T10:05:00",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_metric_anomalies(collected_data)
        
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "metric_drop"
        assert anomalies[0]["severity"] == "high"
    
    def test_identify_multiple_metric_anomalies(self):
        """Test identifying both spike and drop in same summary."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "prometheus": {
                "source": "prometheus",
                "count": 120,
                "summary": "spike detected: 7.30 (avg: 0.85); drop detected: 0.05 (avg: 2.50)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_metric_anomalies(collected_data)
        
        assert len(anomalies) == 2
        assert any(a["type"] == "metric_spike" for a in anomalies)
        assert any(a["type"] == "metric_drop" for a in anomalies)
    
    def test_no_metric_anomalies(self):
        """Test no anomalies when metrics are normal."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "prometheus": {
                "source": "prometheus",
                "count": 120,
                "summary": "2 time series, 120 data points; metrics: http_requests_total",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_metric_anomalies(collected_data)
        
        assert len(anomalies) == 0
    
    def test_skip_failed_sources(self):
        """Test skipping failed data sources."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "prometheus": {
                "source": "prometheus",
                "error": "Connection failed",
                "status": "failed"
            }
        }
        
        anomalies = agent._identify_metric_anomalies(collected_data)
        
        assert len(anomalies) == 0


class TestLogAnomalyDetection:
    """Test log anomaly detection."""
    
    def test_identify_error_rate_spike_high(self):
        """Test identifying high error rate spike (>50%)."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 100,
                "summary": "100 logs (60 ERROR, 40 INFO), top error: 'NullPointerException' (45x)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_log_anomalies(collected_data)
        
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "error_rate_spike"
        assert anomalies[0]["severity"] == "critical"
        assert "60/100" in anomalies[0]["description"]
        assert anomalies[0]["error_rate"] == 0.6
    
    def test_identify_error_rate_spike_moderate(self):
        """Test identifying moderate error rate spike (20-50%)."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 100,
                "summary": "100 logs (30 ERROR, 70 INFO), top error: 'ConnectionError' (20x)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_log_anomalies(collected_data)
        
        assert len(anomalies) == 1
        assert anomalies[0]["type"] == "error_rate_spike"
        assert anomalies[0]["severity"] == "high"
        assert anomalies[0]["error_rate"] == 0.3
    
    def test_no_log_anomalies_low_error_rate(self):
        """Test no anomaly when error rate is low (<20%)."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 100,
                "summary": "100 logs (10 ERROR, 90 INFO), top error: 'TimeoutWarning' (5x)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_log_anomalies(collected_data)
        
        assert len(anomalies) == 0
    
    def test_handle_fatal_errors(self):
        """Test handling FATAL level errors."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 50,
                "summary": "50 logs (25 FATAL, 25 INFO), top error: 'OutOfMemory' (20x)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = agent._identify_log_anomalies(collected_data)
        
        assert len(anomalies) == 1
        assert anomalies[0]["severity"] == "critical"


class TestErrorClustering:
    """Test error message clustering."""
    
    def test_cluster_single_error(self):
        """Test clustering single error pattern."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 100,
                "summary": "100 logs, top error: 'NullPointerException at line 57' (45x)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        clusters = agent._cluster_errors(collected_data)
        
        assert len(clusters) == 1
        assert clusters[0]["count"] == 45
        assert "NullPointerException" in clusters[0]["pattern"]
    
    def test_cluster_multiple_errors(self):
        """Test clustering multiple different errors."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 100,
                "summary": "100 logs, top errors: 'NullPointerException' (45x), 'TimeoutError' (10x)",
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        clusters = agent._cluster_errors(collected_data)
        
        assert len(clusters) == 2
        # Should be sorted by count
        assert clusters[0]["count"] >= clusters[1]["count"]
    
    def test_cluster_normalization(self):
        """Test error message normalization in clustering."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        # Test normalization
        msg1 = "Error at line 123: Connection timeout"
        msg2 = "Error at line 456: Connection timeout"
        
        norm1 = agent._normalize_error_message(msg1)
        norm2 = agent._normalize_error_message(msg2)
        
        # Should normalize to same pattern (numbers replaced)
        assert norm1 == norm2
        assert "N" in norm1
    
    def test_normalize_uuids(self):
        """Test UUID normalization."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        msg = "Request failed for ID: 550e8400-e29b-41d4-a716-446655440000"
        normalized = agent._normalize_error_message(msg)
        
        assert "UUID" in normalized
        assert "550e8400" not in normalized
    
    def test_normalize_hex_values(self):
        """Test hex value normalization."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        msg = "Memory address: 0x7fff5fbff8a0"
        normalized = agent._normalize_error_message(msg)
        
        assert "HEX" in normalized
        assert "7fff" not in normalized
    
    def test_normalize_file_paths(self):
        """Test file path normalization."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        msg = "File not found: /var/log/app/server.log"
        normalized = agent._normalize_error_message(msg)
        
        assert "/PATH" in normalized
        assert "/var/log" not in normalized
    
    def test_extract_stack_trace(self):
        """Test stack trace extraction from error pattern."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        pattern = "Error in charge.go:112 called from payment.go:57"
        stack_trace = agent._extract_stack_trace(pattern)
        
        assert stack_trace is not None
        assert "charge.go:112" in stack_trace
        assert "payment.go:57" in stack_trace
    
    def test_no_stack_trace(self):
        """Test no stack trace when pattern doesn't contain file:line."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        pattern = "Generic connection error"
        stack_trace = agent._extract_stack_trace(pattern)
        
        assert stack_trace is None


class TestTimelineBuilding:
    """Test incident timeline building."""
    
    def test_build_timeline_with_anomalies(self):
        """Test building timeline with anomalies."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {
            "kubernetes": {
                "source": "kubernetes",
                "count": 100,
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
        
        anomalies = [
            {
                "type": "error_rate_spike",
                "timestamp": "2025-10-14T08:05:00",
                "severity": "critical",
                "description": "Error rate increased"
            }
        ]
        
        timeline = agent._build_timeline(collected_data, anomalies)
        
        assert len(timeline) >= 2  # At least context + anomaly
        # Check that anomaly is in timeline
        assert any("error_rate_spike" in event["event"] for event in timeline)
        # Check chronological order
        for i in range(len(timeline) - 1):
            assert timeline[i]["time"] <= timeline[i + 1]["time"]
    
    def test_timeline_chronological_order(self):
        """Test timeline events are in chronological order."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {}
        anomalies = [
            {
                "type": "spike",
                "timestamp": "2025-10-14T08:10:00",
                "severity": "high",
                "description": "Second event"
            },
            {
                "type": "drop",
                "timestamp": "2025-10-14T08:05:00",
                "severity": "medium",
                "description": "First event"
            }
        ]
        
        timeline = agent._build_timeline(collected_data, anomalies)
        
        # Should be sorted by time
        timestamps = [event["time"] for event in timeline]
        assert timestamps == sorted(timestamps)
    
    def test_empty_timeline(self):
        """Test building timeline with no data."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        timeline = agent._build_timeline({}, [])
        
        assert isinstance(timeline, list)
        assert len(timeline) == 0


class TestDataCorrelation:
    """Test data correlation across sources."""
    
    def test_correlate_metric_and_log_spikes(self):
        """Test correlating metric spike with error spike."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {}
        analysis = {
            "anomalies": [
                {
                    "type": "metric_spike",
                    "timestamp": "2025-10-14T08:05:00",
                    "severity": "critical",
                    "description": "Response time spike"
                },
                {
                    "type": "error_rate_spike",
                    "timestamp": "2025-10-14T08:05:30",
                    "severity": "critical",
                    "description": "Error rate increase"
                }
            ]
        }
        
        correlations = agent._correlate_data(collected_data, analysis)
        
        assert len(correlations) >= 1
        assert any(c["type"] == "temporal_alignment" for c in correlations)
    
    def test_no_correlation_distant_timestamps(self):
        """Test no correlation when timestamps are far apart."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {}
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {}
        analysis = {
            "anomalies": [
                {
                    "type": "metric_spike",
                    "timestamp": "2025-10-14T08:00:00",
                    "severity": "critical",
                    "description": "Metric spike"
                },
                {
                    "type": "error_rate_spike",
                    "timestamp": "2025-10-14T09:00:00",
                    "severity": "critical",
                    "description": "Error spike"
                }
            ]
        }
        
        correlations = agent._correlate_data(collected_data, analysis)
        
        # Should not correlate events 1 hour apart
        temporal_corr = [c for c in correlations if c["type"] == "temporal_alignment"]
        assert len(temporal_corr) == 0
    
    def test_deployment_correlation(self):
        """Test correlation with deployment mentioned in problem."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = {
            "description": "Errors started after v1.19 deployment at 08:04"
        }
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        collected_data = {}
        analysis = {
            "anomalies": [
                {
                    "type": "error_rate_spike",
                    "timestamp": "2025-10-14T08:05:00",
                    "severity": "critical",
                    "description": "Error spike"
                }
            ]
        }
        
        correlations = agent._correlate_data(collected_data, analysis)
        
        assert any(c["type"] == "deployment_correlation" for c in correlations)
    
    def test_timestamps_close(self):
        """Test timestamp proximity checking."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        # Test close timestamps (3 minutes apart)
        ts1 = "2025-10-14T08:00:00"
        ts2 = "2025-10-14T08:03:00"
        
        assert agent._timestamps_close(ts1, ts2, threshold_minutes=5) is True
        
        # Test distant timestamps (10 minutes apart)
        ts3 = "2025-10-14T08:10:00"
        
        assert agent._timestamps_close(ts1, ts3, threshold_minutes=5) is False
    
    def test_timestamps_close_invalid(self):
        """Test timestamp proximity with invalid timestamps."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        # Test with None
        assert agent._timestamps_close(None, "2025-10-14T08:00:00") is False
        
        # Test with invalid format
        assert agent._timestamps_close("invalid", "2025-10-14T08:00:00") is False


class TestExecuteIntegration:
    """Test full agent execution."""
    
    def test_execute_success(self):
        """Test successful execution with data."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.DATA_COLLECTED: {
                "kubernetes": {
                    "source": "kubernetes",
                    "count": 100,
                    "summary": "100 logs (45 ERROR, 55 INFO), top error: 'NullPointerException' (45x)",
                    "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
                }
            },
            ScratchpadSection.PROBLEM_DESCRIPTION: {
                "description": "API errors after deployment",
                "time_window": "2h"
            }
        }.get(section, {})
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        result = agent.execute()
        
        assert result["success"] is True
        assert result["anomalies_found"] >= 0
        assert result["error_clusters_found"] >= 0
        assert result["timeline_events"] >= 0
        assert result["correlation_count"] >= 0
        
        # Verify scratchpad was updated
        scratchpad.write_section.assert_called_once()
        section, analysis = scratchpad.write_section.call_args[0]
        assert section == ScratchpadSection.PATTERN_ANALYSIS
        assert "anomalies" in analysis
        assert "error_clusters" in analysis
        assert "timeline" in analysis
        assert "correlations" in analysis
    
    def test_execute_no_data_error(self):
        """Test execution fails when no data collected."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = None
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        with pytest.raises(ValueError, match="No data collected"):
            agent.execute()
    
    def test_execute_with_metrics_and_logs(self):
        """Test execution with both metrics and logs."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.DATA_COLLECTED: {
                "kubernetes": {
                    "source": "kubernetes",
                    "count": 100,
                    "summary": "100 logs (45 ERROR, 55 INFO), top error: 'NullPointerException' (40x)",
                    "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
                },
                "prometheus": {
                    "source": "prometheus",
                    "count": 120,
                    "summary": "spike detected: 7.30 (avg: 0.85) at 2025-10-14T08:05:00",
                    "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
                }
            },
            ScratchpadSection.PROBLEM_DESCRIPTION: {}
        }.get(section, {})
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        result = agent.execute()
        
        assert result["success"] is True
        # Should find anomalies in both sources
        assert result["anomalies_found"] >= 2
    
    def test_execute_with_failed_sources(self):
        """Test execution handles failed data sources."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.DATA_COLLECTED: {
                "kubernetes": {
                    "source": "kubernetes",
                    "error": "Connection failed",
                    "status": "failed"
                },
                "prometheus": {
                    "source": "prometheus",
                    "count": 120,
                    "summary": "spike detected: 7.30 (avg: 0.85)",
                    "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
                }
            },
            ScratchpadSection.PROBLEM_DESCRIPTION: {}
        }.get(section, {})
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        result = agent.execute()
        
        # Should still succeed with partial data
        assert result["success"] is True


class TestHelperMethods:
    """Test helper utility methods."""
    
    def test_extract_timestamp_from_summary(self):
        """Test extracting timestamp from summary text."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        summary = "spike detected: 7.30 at 2025-10-14T10:05:00"
        timestamp = agent._extract_timestamp_from_summary(summary)
        
        assert "2025-10-14T10:05:00" in timestamp
    
    def test_extract_timestamp_fallback(self):
        """Test timestamp extraction fallback to current time."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        summary = "spike detected but no timestamp"
        timestamp = agent._extract_timestamp_from_summary(summary)
        
        # Should return a valid timestamp
        assert isinstance(timestamp, str)
        assert len(timestamp) > 0
    
    def test_extract_anomaly_description(self):
        """Test extracting anomaly description."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        summary = "2 time series; spike detected: 7.30 (avg: 0.85); no other issues"
        description = agent._extract_anomaly_description(summary, "spike")
        
        assert "spike detected" in description
        assert "7.30" in description
    
    def test_extract_error_count(self):
        """Test extracting error count from summary."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        summary = "100 logs (45 ERROR, 55 INFO)"
        count = agent._extract_error_count(summary)
        
        assert count == 45
    
    def test_extract_error_count_none(self):
        """Test extracting error count when not present."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        summary = "100 logs, all INFO level"
        count = agent._extract_error_count(summary)
        
        assert count == 0
    
    def test_extract_start_time(self):
        """Test extracting start time from source data."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        source_data = {
            "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
        }
        
        start_time = agent._extract_start_time(source_data)
        
        assert start_time == "2025-10-14T08:00:00"
    
    def test_extract_start_time_fallback(self):
        """Test extracting start time fallback."""
        config = {"llm": {"default_model": "gpt-4o"}}
        scratchpad = Mock(spec=Scratchpad)
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        source_data = {}
        start_time = agent._extract_start_time(source_data)
        
        # Should return a valid timestamp
        assert isinstance(start_time, str)
        assert len(start_time) > 0
