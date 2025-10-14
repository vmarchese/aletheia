"""Unit tests for data summarization module."""

import pytest
from datetime import datetime, timedelta
from aletheia.fetchers.summarization import LogSummarizer, MetricSummarizer


class TestLogSummarizer:
    """Tests for LogSummarizer class."""

    def test_empty_logs(self):
        """Test summarization of empty log list."""
        summarizer = LogSummarizer()
        result = summarizer.summarize([])

        assert result["count"] == 0
        assert result["level_counts"] == {}
        assert result["error_clusters"] == {}
        assert result["top_errors"] == []
        assert result["summary"] == "No logs found"

    def test_basic_log_summary(self):
        """Test basic log summarization with multiple levels."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "INFO", "message": "Application started"},
            {"level": "INFO", "message": "Request processed"},
            {"level": "ERROR", "message": "Connection failed"},
            {"level": "WARN", "message": "Slow query detected"},
        ]

        result = summarizer.summarize(logs)

        assert result["count"] == 4
        assert result["level_counts"] == {"INFO": 2, "ERROR": 1, "WARN": 1}
        assert "4 logs" in result["summary"]

    def test_error_clustering(self):
        """Test error pattern clustering."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "ERROR", "message": "NullPointerException at line 42"},
            {"level": "ERROR", "message": "NullPointerException at line 89"},
            {"level": "ERROR", "message": "NullPointerException at line 123"},
            {"level": "ERROR", "message": "Connection timeout"},
            {"level": "ERROR", "message": "Connection timeout"},
        ]

        result = summarizer.summarize(logs)

        assert result["count"] == 5
        assert len(result["error_clusters"]) > 0
        assert result["top_errors"][0][1] == 3  # NullPointerException appears 3 times

    def test_error_pattern_extraction(self):
        """Test error pattern extraction and normalization."""
        summarizer = LogSummarizer()

        # Test with colon separator (takes first part before colon)
        pattern1 = summarizer._extract_error_pattern("NullPointerException: variable x is null")
        assert pattern1 == "NullPointerException"

        # Test UUID normalization
        pattern2 = summarizer._extract_error_pattern(
            "Failed to process request a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        )
        assert "<UUID>" in pattern2

        # Test number normalization
        pattern3 = summarizer._extract_error_pattern("Error code 12345")
        assert "<NUM>" in pattern3

        # Test hex normalization
        pattern4 = summarizer._extract_error_pattern("Memory address 0xdeadbeef")
        assert "<HEX>" in pattern4

        # Test path normalization (no colon, so path is included)
        pattern5 = summarizer._extract_error_pattern("File not found /var/log/app.log")
        assert "<PATH>" in pattern5

    def test_top_errors_ordering(self):
        """Test that top errors are ordered by frequency."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "ERROR", "message": "Error A"},
            {"level": "ERROR", "message": "Error B"},
            {"level": "ERROR", "message": "Error B"},
            {"level": "ERROR", "message": "Error C"},
            {"level": "ERROR", "message": "Error C"},
            {"level": "ERROR", "message": "Error C"},
        ]

        result = summarizer.summarize(logs)
        top_errors = result["top_errors"]

        assert len(top_errors) == 3
        assert top_errors[0][0] == "Error C"
        assert top_errors[0][1] == 3
        assert top_errors[1][0] == "Error B"
        assert top_errors[1][1] == 2

    def test_time_range_extraction(self):
        """Test time range extraction from logs."""
        summarizer = LogSummarizer()
        now = datetime.now()
        logs = [
            {"level": "INFO", "message": "Log 1", "timestamp": now.isoformat()},
            {"level": "INFO", "message": "Log 2", "timestamp": (now + timedelta(hours=1)).isoformat()},
            {"level": "INFO", "message": "Log 3", "timestamp": (now + timedelta(hours=2)).isoformat()},
        ]

        result = summarizer.summarize(logs)
        start, end = result["time_range"]

        assert start is not None
        assert end is not None
        assert end > start
        assert (end - start).total_seconds() >= 7200  # At least 2 hours

    def test_time_range_with_z_suffix(self):
        """Test time range extraction with Z (Zulu) suffix."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "INFO", "message": "Log 1", "timestamp": "2025-10-14T10:00:00Z"},
            {"level": "INFO", "message": "Log 2", "timestamp": "2025-10-14T11:00:00Z"},
        ]

        result = summarizer.summarize(logs)
        start, end = result["time_range"]

        assert start is not None
        assert end is not None

    def test_time_range_missing_timestamps(self):
        """Test time range when logs have no timestamps."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "INFO", "message": "Log 1"},
            {"level": "INFO", "message": "Log 2"},
        ]

        result = summarizer.summarize(logs)
        start, end = result["time_range"]

        assert start is None
        assert end is None

    def test_summary_text_format(self):
        """Test human-readable summary text format."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "INFO", "message": "Message 1"},
            {"level": "ERROR", "message": "Database connection failed"},
            {"level": "ERROR", "message": "Database connection failed"},
        ]

        result = summarizer.summarize(logs)

        assert "3 logs" in result["summary"]
        assert "ERROR" in result["summary"]
        assert "INFO" in result["summary"]
        assert "Database connection failed" in result["summary"]

    def test_level_normalization(self):
        """Test that log levels are normalized to uppercase."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "info", "message": "Log 1"},
            {"level": "Info", "message": "Log 2"},
            {"level": "INFO", "message": "Log 3"},
        ]

        result = summarizer.summarize(logs)

        assert result["level_counts"]["INFO"] == 3

    def test_missing_level_defaults_to_info(self):
        """Test that missing log level defaults to INFO."""
        summarizer = LogSummarizer()
        logs = [
            {"message": "Log without level"},
        ]

        result = summarizer.summarize(logs)

        assert result["level_counts"]["INFO"] == 1

    def test_multiple_timestamp_fields(self):
        """Test extraction from multiple timestamp field names."""
        summarizer = LogSummarizer()
        now = datetime.now()

        logs = [
            {"level": "INFO", "timestamp": now.isoformat()},
            {"level": "INFO", "time": (now + timedelta(hours=1)).isoformat()},
            {"level": "INFO", "ts": (now + timedelta(hours=2)).isoformat()},
            {"level": "INFO", "@timestamp": (now + timedelta(hours=3)).isoformat()},
        ]

        result = summarizer.summarize(logs)
        start, end = result["time_range"]

        assert start is not None
        assert end is not None

    def test_critical_level_in_errors(self):
        """Test that CRITICAL level is treated as error."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "CRITICAL", "message": "System failure"},
            {"level": "FATAL", "message": "Fatal error"},
        ]

        result = summarizer.summarize(logs)

        assert len(result["error_clusters"]) == 2

    def test_empty_error_messages(self):
        """Test handling of empty error messages."""
        summarizer = LogSummarizer()
        logs = [
            {"level": "ERROR", "message": ""},
            {"level": "ERROR"},
        ]

        result = summarizer.summarize(logs)

        # Should not crash, clusters may be empty
        assert result["count"] == 2

    def test_long_error_messages(self):
        """Test handling of very long error messages."""
        summarizer = LogSummarizer()
        long_message = "Error " + ("x" * 200)
        logs = [
            {"level": "ERROR", "message": long_message},
        ]

        result = summarizer.summarize(logs)

        # Pattern should be truncated
        if result["top_errors"]:
            pattern = result["top_errors"][0][0]
            assert len(pattern) <= 100  # Should be limited

    def test_provided_time_range(self):
        """Test using provided time range instead of extracting."""
        summarizer = LogSummarizer()
        provided_range = (datetime(2025, 10, 14, 10, 0), datetime(2025, 10, 14, 12, 0))
        logs = [
            {"level": "INFO", "message": "Log 1"},
        ]

        result = summarizer.summarize(logs, time_range=provided_range)

        assert result["time_range"] == provided_range


class TestMetricSummarizer:
    """Tests for MetricSummarizer class."""

    def test_empty_metrics(self):
        """Test summarization of empty metrics list."""
        summarizer = MetricSummarizer()
        result = summarizer.summarize([])

        assert result["num_series"] == 0
        assert result["total_points"] == 0
        assert result["metric_names"] == set()
        assert result["anomalies"] == []
        assert "No data" in result["summary"]

    def test_empty_metrics_with_query(self):
        """Test empty metrics with query context."""
        summarizer = MetricSummarizer()
        result = summarizer.summarize([], query="rate(http_requests[5m])")

        assert "rate(http_requests[5m])" in result["summary"]

    def test_basic_metric_summary(self):
        """Test basic metric summarization."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "http_requests_total", "status": "200"},
                "values": [[1697280000, "100"], [1697280060, "110"], [1697280120, "120"]]
            },
            {
                "metric": {"__name__": "http_requests_total", "status": "500"},
                "values": [[1697280000, "5"], [1697280060, "6"]]
            }
        ]

        result = summarizer.summarize(metrics)

        assert result["num_series"] == 2
        assert result["total_points"] == 5
        assert "http_requests_total" in result["metric_names"]

    def test_metric_name_extraction(self):
        """Test extraction of metric names."""
        summarizer = MetricSummarizer()
        metrics = [
            {"metric": {"__name__": "cpu_usage"}, "values": [[1, "50"]]},
            {"metric": {"__name__": "memory_usage"}, "values": [[1, "75"]]},
        ]

        result = summarizer.summarize(metrics)

        assert result["metric_names"] == {"cpu_usage", "memory_usage"}

    def test_metric_name_fallback(self):
        """Test metric name extraction without __name__ label."""
        summarizer = MetricSummarizer()
        metrics = [
            {"metric": {"service": "payments", "status": "200"}, "values": [[1, "100"]]},
        ]

        result = summarizer.summarize(metrics)

        # Should use first non-internal label
        assert "payments" in result["metric_names"] or "200" in result["metric_names"]

    def test_spike_detection(self):
        """Test detection of metric spikes."""
        summarizer = MetricSummarizer(spike_threshold=3.0)
        metrics = [
            {
                "metric": {"__name__": "error_rate"},
                "values": [
                    [1697280000, "1.0"],
                    [1697280060, "1.0"],
                    [1697280120, "1.0"],
                    [1697280180, "15.0"],  # Spike (15 vs avg ~4.5, 15 > 4.5*3.0=13.5)
                ]
            }
        ]

        result = summarizer.summarize(metrics)

        assert len(result["anomalies"]) > 0
        assert result["anomalies"][0]["type"] == "spike"
        assert result["anomalies"][0]["value"] == 15.0

    def test_drop_detection(self):
        """Test detection of metric drops."""
        summarizer = MetricSummarizer(drop_threshold=0.33)
        metrics = [
            {
                "metric": {"__name__": "throughput"},
                "values": [
                    [1697280000, "100.0"],
                    [1697280060, "100.0"],
                    [1697280120, "10.0"],  # Drop (0.1x average)
                ]
            }
        ]

        result = summarizer.summarize(metrics)

        assert len(result["anomalies"]) > 0
        assert result["anomalies"][0]["type"] == "drop"
        assert result["anomalies"][0]["value"] == 10.0

    def test_nan_value_handling(self):
        """Test handling of NaN values in metrics."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "metric_with_nan"},
                "values": [
                    [1697280000, "100"],
                    [1697280060, "NaN"],
                    [1697280120, "100"],
                ]
            }
        ]

        result = summarizer.summarize(metrics)

        # Should not crash and should skip NaN values
        assert result["num_series"] == 1
        assert result["total_points"] == 3

    def test_inf_value_handling(self):
        """Test handling of Inf values in metrics."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "metric_with_inf"},
                "values": [
                    [1697280000, "100"],
                    [1697280060, "Inf"],
                    [1697280120, "100"],
                ]
            }
        ]

        result = summarizer.summarize(metrics)

        # Should not crash
        assert result["num_series"] == 1

    def test_rate_of_change_calculation(self):
        """Test calculation of rate of change."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "counter"},
                "values": [
                    [1697280000, "100"],  # t=0, v=100
                    [1697280060, "160"],  # t=60, v=160 (rate=1.0/sec)
                ]
            }
        ]

        result = summarizer.summarize(metrics)

        assert result["rate_of_change"] is not None
        assert abs(result["rate_of_change"] - 1.0) < 0.01  # Approximately 1.0/sec

    def test_rate_of_change_insufficient_data(self):
        """Test rate of change with insufficient data."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "counter"},
                "values": [[1697280000, "100"]]  # Only one point
            }
        ]

        result = summarizer.summarize(metrics)

        assert result["rate_of_change"] is None

    def test_anomaly_ordering(self):
        """Test that anomalies are ordered by severity."""
        summarizer = MetricSummarizer(spike_threshold=2.0)
        metrics = [
            {
                "metric": {"__name__": "metric1"},
                "values": [[1, "10"], [2, "10"], [3, "50"]]  # Spike to 50 (avg=23.3, 50>46.6)
            },
            {
                "metric": {"__name__": "metric2"},
                "values": [[1, "10"], [2, "10"], [3, "100"]]  # Bigger spike to 100 (avg=40, 100>80)
            }
        ]

        result = summarizer.summarize(metrics)

        # Bigger spike should be first
        assert result["anomalies"][0]["value"] == 100.0

    def test_summary_text_format(self):
        """Test human-readable summary text format."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "cpu_usage"},
                "values": [[1, "50"], [2, "51"]]
            }
        ]

        result = summarizer.summarize(metrics)

        assert "1 time series" in result["summary"]
        assert "2 data points" in result["summary"]
        assert "cpu_usage" in result["summary"]

    def test_anomaly_in_summary(self):
        """Test that anomalies appear in summary text."""
        summarizer = MetricSummarizer(spike_threshold=2.0)
        metrics = [
            {
                "metric": {"__name__": "error_rate"},
                "values": [[1, "1"], [2, "1"], [3, "20"]]  # Clear spike (avg=7.33, 20>14.66)
            }
        ]

        result = summarizer.summarize(metrics)

        assert "spike" in result["summary"] or "anomalies" in result["summary"]

    def test_multiple_series_aggregation(self):
        """Test aggregation across multiple series."""
        summarizer = MetricSummarizer()
        metrics = [
            {"metric": {"__name__": "m1"}, "values": [[1, "1"], [2, "2"]]},
            {"metric": {"__name__": "m2"}, "values": [[1, "3"], [2, "4"], [3, "5"]]},
            {"metric": {"__name__": "m3"}, "values": [[1, "6"]]},
        ]

        result = summarizer.summarize(metrics)

        assert result["num_series"] == 3
        assert result["total_points"] == 6

    def test_zero_average_no_spike(self):
        """Test that zero average doesn't trigger false spike."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "zeros"},
                "values": [[1, "0"], [2, "0"], [3, "0"]]
            }
        ]

        result = summarizer.summarize(metrics)

        # Should not detect spike when all values are zero
        assert len(result["anomalies"]) == 0

    def test_negative_values_handling(self):
        """Test handling of negative metric values."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "delta"},
                "values": [[1, "-10"], [2, "10"], [3, "-5"]]
            }
        ]

        result = summarizer.summarize(metrics)

        # Should not crash with negative values
        assert result["num_series"] == 1

    def test_custom_thresholds(self):
        """Test custom spike and drop thresholds."""
        # Very sensitive thresholds
        summarizer = MetricSummarizer(spike_threshold=1.5, drop_threshold=0.5)
        metrics = [
            {
                "metric": {"__name__": "sensitive"},
                "values": [[1, "10"], [2, "10"], [3, "10"], [4, "25"]]  # avg=13.75, 25>20.625
            }
        ]

        result = summarizer.summarize(metrics)

        # Should detect spike with lower threshold (25 > 13.75 * 1.5 = 20.625)
        assert len(result["anomalies"]) > 0

    def test_max_anomalies_limit(self):
        """Test that anomaly list is limited to top 5."""
        summarizer = MetricSummarizer(spike_threshold=1.5)
        # Create many series with spikes
        metrics = [
            {
                "metric": {"__name__": f"metric{i}"},
                "values": [[1, "1"], [2, f"{10 + i}"]]
            }
            for i in range(10)
        ]

        result = summarizer.summarize(metrics)

        # Should limit to top 5
        assert len(result["anomalies"]) <= 5

    def test_invalid_value_format(self):
        """Test handling of invalid value formats."""
        summarizer = MetricSummarizer()
        metrics = [
            {
                "metric": {"__name__": "invalid"},
                "values": [
                    [1, "100"],
                    [2, "not_a_number"],
                    [3, "200"]
                ]
            }
        ]

        result = summarizer.summarize(metrics)

        # Should not crash, may skip invalid values
        assert result["num_series"] == 1

    def test_empty_values_list(self):
        """Test handling of empty values list."""
        summarizer = MetricSummarizer()
        metrics = [
            {"metric": {"__name__": "empty"}, "values": []}
        ]

        result = summarizer.summarize(metrics)

        assert result["total_points"] == 0

    def test_single_value_no_rate(self):
        """Test that single value doesn't produce rate of change."""
        summarizer = MetricSummarizer()
        metrics = [
            {"metric": {"__name__": "single"}, "values": [[1, "100"]]}
        ]

        result = summarizer.summarize(metrics)

        assert result["rate_of_change"] is None
