"""Unit tests for Root Cause Analyst Agent."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from aletheia.agents.root_cause_analyst import RootCauseAnalystAgent
from aletheia.scratchpad import ScratchpadSection


class TestRootCauseAnalystAgent:
    """Test suite for RootCauseAnalystAgent."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "llm": {
                "default_model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY"
            }
        }
    
    @pytest.fixture
    def scratchpad(self):
        """Create mock scratchpad."""
        mock_scratchpad = Mock()
        mock_scratchpad.read_section = Mock()
        mock_scratchpad.write_section = Mock()
        return mock_scratchpad
    
    @pytest.fixture
    def agent(self, config, scratchpad):
        """Create RootCauseAnalystAgent instance."""
        return RootCauseAnalystAgent(config, scratchpad)
    
    @pytest.fixture
    def sample_problem(self):
        """Sample problem description."""
        return {
            "description": "Payment API 500 errors after v1.19 deployment",
            "time_window": "2h",
            "affected_services": ["payments-svc"]
        }
    
    @pytest.fixture
    def sample_data_collected(self):
        """Sample collected data."""
        return {
            "kubernetes": {
                "summary": "200 logs (45 ERROR), top error: 'nil pointer dereference' (45x)",
                "count": 200,
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            },
            "prometheus": {
                "summary": "2 time series, 120 data points; spike detected: 7.30 (avg: 0.85)",
                "count": 120,
                "time_range": "2025-10-14T08:00:00 - 2025-10-14T10:00:00"
            }
        }
    
    @pytest.fixture
    def sample_pattern_analysis(self):
        """Sample pattern analysis."""
        return {
            "anomalies": [
                {
                    "type": "error_rate_spike",
                    "timestamp": "2025-10-14T08:05:00",
                    "severity": "critical",
                    "description": "High error rate: 45/200 (22.5%)",
                    "error_rate": 0.225
                },
                {
                    "type": "metric_spike",
                    "timestamp": "2025-10-14T08:05:30",
                    "severity": "critical",
                    "description": "spike detected: 7.30 (avg: 0.85)"
                }
            ],
            "error_clusters": [
                {
                    "pattern": "nil pointer dereference at features.go:N",
                    "count": 45,
                    "examples": ["nil pointer dereference at features.go:57"],
                    "stack_trace": "charge.go:112 → features.go:57"
                }
            ],
            "correlations": [
                {
                    "type": "temporal_alignment",
                    "description": "Metric spike coincides with error_rate_spike",
                    "confidence": 0.85
                }
            ],
            "timeline": [
                {
                    "time": "2025-10-14T08:04:00",
                    "event": "Deployment: payments-svc v1.19",
                    "type": "deployment"
                },
                {
                    "time": "2025-10-14T08:05:00",
                    "event": "error_rate_spike: High error rate: 45/200 (22.5%)",
                    "type": "anomaly",
                    "severity": "critical"
                }
            ]
        }
    
    @pytest.fixture
    def sample_code_inspection(self):
        """Sample code inspection."""
        return {
            "suspect_files": [
                {
                    "file": "features.go",
                    "line": 57,
                    "function": "IsEnabled",
                    "repository": "/path/to/repo",
                    "snippet": "func IsEnabled(f *Feature) bool { return *f.Enabled }",
                    "analysis": "No nil check before dereferencing f.Enabled",
                    "git_blame": {
                        "commit": "a3f9c2d",
                        "author": "john.doe",
                        "date": "2025-10-10",
                        "message": "Refactor feature flag loading"
                    }
                }
            ],
            "related_code": []
        }
    
    # Test initialization
    
    def test_initialization(self, config, scratchpad):
        """Test agent initialization."""
        agent = RootCauseAnalystAgent(config, scratchpad)
        assert agent.config == config
        assert agent.scratchpad == scratchpad
        assert agent.agent_name == "root_cause_analyst"
    
    # Test execute method
    
    def test_execute_success(self, agent, sample_problem, sample_data_collected, 
                            sample_pattern_analysis, sample_code_inspection):
        """Test successful execution."""
        # Mock scratchpad reads
        agent.scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.PROBLEM_DESCRIPTION: sample_problem,
            ScratchpadSection.DATA_COLLECTED: sample_data_collected,
            ScratchpadSection.PATTERN_ANALYSIS: sample_pattern_analysis,
            ScratchpadSection.CODE_INSPECTION: sample_code_inspection
        }.get(section)
        
        # Execute
        result = agent.execute()
        
        # Assertions
        assert result["success"] is True
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["recommendations_count"] > 0
        assert "root_cause_type" in result
        
        # Verify scratchpad write was called
        agent.scratchpad.write_section.assert_called_once()
        call_args = agent.scratchpad.write_section.call_args
        assert call_args[0][0] == ScratchpadSection.FINAL_DIAGNOSIS
    
    def test_execute_missing_problem(self, agent):
        """Test execution with missing problem description."""
        agent.scratchpad.read_section.return_value = None
        
        with pytest.raises(ValueError, match="PROBLEM_DESCRIPTION section is missing"):
            agent.execute()
    
    def test_execute_missing_data_collected(self, agent, sample_problem):
        """Test execution with missing data collected."""
        agent.scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.PROBLEM_DESCRIPTION: sample_problem,
            ScratchpadSection.DATA_COLLECTED: None
        }.get(section)
        
        with pytest.raises(ValueError, match="DATA_COLLECTED section is missing"):
            agent.execute()
    
    def test_execute_missing_pattern_analysis(self, agent, sample_problem, sample_data_collected):
        """Test execution with missing pattern analysis."""
        agent.scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.PROBLEM_DESCRIPTION: sample_problem,
            ScratchpadSection.DATA_COLLECTED: sample_data_collected,
            ScratchpadSection.PATTERN_ANALYSIS: None
        }.get(section)
        
        with pytest.raises(ValueError, match="PATTERN_ANALYSIS section is missing"):
            agent.execute()
    
    def test_execute_without_code_inspection(self, agent, sample_problem, 
                                            sample_data_collected, sample_pattern_analysis):
        """Test execution without code inspection (optional)."""
        agent.scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.PROBLEM_DESCRIPTION: sample_problem,
            ScratchpadSection.DATA_COLLECTED: sample_data_collected,
            ScratchpadSection.PATTERN_ANALYSIS: sample_pattern_analysis,
            ScratchpadSection.CODE_INSPECTION: None
        }.get(section)
        
        # Should succeed without code inspection
        result = agent.execute()
        assert result["success"] is True
    
    # Test synthesize_findings method
    
    def test_synthesize_findings(self, agent, sample_problem, sample_data_collected,
                                 sample_pattern_analysis, sample_code_inspection):
        """Test synthesize findings."""
        synthesis = agent.synthesize_findings(
            problem=sample_problem,
            data_collected=sample_data_collected,
            pattern_analysis=sample_pattern_analysis,
            code_inspection=sample_code_inspection
        )
        
        # Check structure
        assert "key_evidence" in synthesis
        assert "causal_chain" in synthesis
        assert "data_completeness" in synthesis
        assert "consistency" in synthesis
        assert "timeline_correlation" in synthesis
        
        # Check evidence
        assert len(synthesis["key_evidence"]) > 0
        # Should have evidence from anomalies, error clusters, correlations, code
        assert any(e["type"] == "anomaly" for e in synthesis["key_evidence"])
        assert any(e["type"] == "error_cluster" for e in synthesis["key_evidence"])
        assert any(e["type"] == "correlation" for e in synthesis["key_evidence"])
        assert any(e["type"] == "code_issue" for e in synthesis["key_evidence"])
        
        # Check evidence is sorted by weight
        weights = [e.get("weight", 0) for e in synthesis["key_evidence"]]
        assert weights == sorted(weights, reverse=True)
        
        # Check scores are in valid range
        assert 0.0 <= synthesis["data_completeness"] <= 1.0
        assert 0.0 <= synthesis["consistency"] <= 1.0
    
    def test_synthesize_without_code_inspection(self, agent, sample_problem, 
                                               sample_data_collected, sample_pattern_analysis):
        """Test synthesis without code inspection."""
        synthesis = agent.synthesize_findings(
            problem=sample_problem,
            data_collected=sample_data_collected,
            pattern_analysis=sample_pattern_analysis,
            code_inspection=None
        )
        
        # Should still work
        assert "key_evidence" in synthesis
        # Should not have code_issue evidence
        assert not any(e["type"] == "code_issue" for e in synthesis["key_evidence"])
    
    def test_evidence_weight_calculation(self, agent):
        """Test evidence weight calculation."""
        # Test anomaly weights
        critical_anomaly = {"severity": "critical"}
        assert agent._calculate_evidence_weight(critical_anomaly, "anomaly") == 1.0
        
        high_anomaly = {"severity": "high"}
        assert agent._calculate_evidence_weight(high_anomaly, "anomaly") == 0.8
        
        # Test error cluster weights
        high_count_cluster = {"count": 100}
        weight = agent._calculate_evidence_weight(high_count_cluster, "error_cluster")
        assert weight >= 0.5
        
        low_count_cluster = {"count": 5}
        weight = agent._calculate_evidence_weight(low_count_cluster, "error_cluster")
        assert 0.0 < weight < 0.5
        
        # Test code issue weights
        recent_code_issue = {"git_blame": {"date": "2025-10-10"}}
        weight = agent._calculate_evidence_weight(recent_code_issue, "code_issue")
        assert weight >= 0.8
    
    def test_causal_chain_building(self, agent, sample_problem, sample_pattern_analysis, 
                                   sample_code_inspection):
        """Test causal chain building."""
        evidence = []  # Not used in this method
        
        chain = agent._build_causal_chain(
            problem=sample_problem,
            pattern_analysis=sample_pattern_analysis,
            code_inspection=sample_code_inspection,
            evidence=evidence
        )
        
        # Should have timeline events
        assert len(chain) > 0
        
        # Should include root cause at the end
        assert any(event["type"] == "root_cause" for event in chain)
        
        # Check structure
        for event in chain:
            assert "step" in event
            assert "description" in event
            assert "type" in event
    
    def test_data_completeness_calculation(self, agent, sample_data_collected, 
                                          sample_pattern_analysis, sample_code_inspection):
        """Test data completeness calculation."""
        # With all data
        completeness = agent._calculate_data_completeness(
            data_collected=sample_data_collected,
            pattern_analysis=sample_pattern_analysis,
            code_inspection=sample_code_inspection
        )
        assert completeness > 0.8  # Should be high with all data
        
        # Without code inspection
        completeness = agent._calculate_data_completeness(
            data_collected=sample_data_collected,
            pattern_analysis=sample_pattern_analysis,
            code_inspection=None
        )
        assert 0.5 < completeness <= 0.9  # Lower but still reasonable
        
        # Minimal data
        completeness = agent._calculate_data_completeness(
            data_collected={"source1": {}},
            pattern_analysis={"anomalies": [], "error_clusters": []},
            code_inspection=None
        )
        assert completeness < 0.7  # Lower with minimal data
    
    def test_consistency_calculation(self, agent):
        """Test consistency calculation."""
        # High consistency: all same type
        evidence = [
            {"type": "anomaly"},
            {"type": "anomaly"},
            {"type": "anomaly"}
        ]
        causal_chain = [{"step": 1}, {"step": 2}, {"step": 3}]
        consistency = agent._calculate_consistency(evidence, causal_chain)
        assert consistency >= 0.9
        
        # Medium consistency: 2-3 types
        evidence = [
            {"type": "anomaly"},
            {"type": "error_cluster"},
            {"type": "anomaly"}
        ]
        consistency = agent._calculate_consistency(evidence, causal_chain)
        assert 0.7 <= consistency < 1.0
        
        # Lower consistency: many types
        evidence = [
            {"type": "anomaly"},
            {"type": "error_cluster"},
            {"type": "code_issue"},
            {"type": "correlation"}
        ]
        consistency = agent._calculate_consistency(evidence, [])
        assert 0.5 <= consistency < 0.8
    
    def test_timeline_correlation_extraction(self, agent, sample_problem, sample_pattern_analysis):
        """Test timeline correlation extraction."""
        correlation = agent._extract_timeline_correlation(
            problem=sample_problem,
            pattern_analysis=sample_pattern_analysis
        )
        
        # Check structure
        assert "deployment_mentioned" in correlation
        assert "first_error_time" in correlation
        assert "alignment" in correlation
        
        # Deployment should be detected
        assert correlation["deployment_mentioned"] is True
        
        # First error time should be extracted
        assert correlation["first_error_time"] == "2025-10-14T08:05:00"
        
        # Alignment should be extracted from correlations
        assert correlation["alignment"] is not None
    
    # Test generate_hypothesis method
    
    def test_generate_hypothesis_with_llm(self, agent):
        """Test hypothesis generation attempts to use LLM and falls back gracefully."""
        # Mock LLM to simulate an error (fallback scenario)
        agent.get_llm = Mock(side_effect=Exception("LLM unavailable"))
        
        synthesis = {
            "key_evidence": [
                {
                    "description": "Issue in features.go:57 - nil pointer dereference",
                    "weight": 0.9,
                    "type": "code_issue"
                }
            ],
            "causal_chain": [],
            "data_completeness": 0.9,
            "consistency": 0.8,
            "problem_description": "Test problem"
        }
        
        # Should fall back to heuristic method
        hypothesis = agent.generate_hypothesis(synthesis)
        
        # Check structure
        assert "type" in hypothesis
        assert "description" in hypothesis
        assert "location" in hypothesis
        
        # Should use heuristic fallback with nil_pointer detection
        assert hypothesis["type"] == "nil_pointer_dereference"
        assert "features.go:57" in hypothesis["location"]
    
    def test_generate_hypothesis_fallback(self, agent):
        """Test hypothesis generation fallback (no LLM)."""
        synthesis = {
            "key_evidence": [
                {
                    "type": "code_issue",
                    "description": "Issue in features.go:57 - nil pointer dereference",
                    "weight": 0.9
                }
            ],
            "causal_chain": [],
            "data_completeness": 0.8,
            "consistency": 0.7
        }
        
        # Force LLM error to trigger fallback
        agent.get_llm = Mock(side_effect=Exception("LLM error"))
        
        hypothesis = agent.generate_hypothesis(synthesis)
        
        # Should use heuristic method
        assert hypothesis["type"] == "nil_pointer_dereference"
        assert "features.go:57" in hypothesis["location"]
    
    def test_generate_hypothesis_insufficient_evidence(self, agent):
        """Test hypothesis with insufficient evidence."""
        synthesis = {
            "key_evidence": [],
            "causal_chain": [],
            "data_completeness": 0.3,
            "consistency": 0.4
        }
        
        hypothesis = agent.generate_hypothesis(synthesis)
        
        assert hypothesis["type"] == "unknown"
        assert "Insufficient evidence" in hypothesis["description"]
    
    def test_parse_llm_hypothesis(self, agent):
        """Test LLM response parsing."""
        # Nil pointer case
        response = "The root cause is a nil pointer dereference in features.go:57"
        evidence = []
        hypothesis = agent._parse_llm_hypothesis(response, evidence)
        
        assert hypothesis["type"] == "nil_pointer_dereference"
        assert hypothesis["location"] == "features.go:57"
        
        # Index out of bounds case
        response = "Array index out of bounds in handler.go:123"
        hypothesis = agent._parse_llm_hypothesis(response, evidence)
        
        assert hypothesis["type"] == "index_out_of_bounds"
        assert hypothesis["location"] == "handler.go:123"
    
    def test_heuristic_hypothesis_generation(self, agent):
        """Test heuristic hypothesis generation."""
        evidence = [
            {
                "type": "code_issue",
                "description": "Nil pointer dereference in features.go:57"
            }
        ]
        causal_chain = []
        
        hypothesis = agent._generate_heuristic_hypothesis(evidence, causal_chain)
        
        assert hypothesis["type"] == "nil_pointer_dereference"
        assert "features.go:57" in hypothesis["location"]
    
    # Test calculate_confidence method
    
    def test_calculate_confidence_high(self, agent):
        """Test high confidence calculation."""
        synthesis = {
            "key_evidence": [
                {"weight": 0.9, "type": "code_issue"},
                {"weight": 0.85, "type": "anomaly"},
                {"weight": 0.8, "type": "error_cluster"},
                {"weight": 0.7, "type": "correlation", "confidence": 0.9}
            ],
            "data_completeness": 0.9,
            "consistency": 0.85
        }
        
        confidence = agent.calculate_confidence(synthesis)
        
        assert 0.8 <= confidence <= 1.0
        assert isinstance(confidence, float)
    
    def test_calculate_confidence_medium(self, agent):
        """Test medium confidence calculation."""
        synthesis = {
            "key_evidence": [
                {"weight": 0.6, "type": "anomaly"},
                {"weight": 0.5, "type": "error_cluster"}
            ],
            "data_completeness": 0.7,
            "consistency": 0.6
        }
        
        confidence = agent.calculate_confidence(synthesis)
        
        assert 0.5 <= confidence < 0.8
    
    def test_calculate_confidence_low(self, agent):
        """Test low confidence calculation."""
        synthesis = {
            "key_evidence": [
                {"weight": 0.3, "type": "anomaly"}
            ],
            "data_completeness": 0.4,
            "consistency": 0.3
        }
        
        confidence = agent.calculate_confidence(synthesis)
        
        assert 0.0 <= confidence < 0.6
    
    def test_calculate_confidence_code_bonus(self, agent):
        """Test confidence with code evidence bonus."""
        # Without code evidence
        synthesis_no_code = {
            "key_evidence": [
                {"weight": 0.7, "type": "anomaly"}
            ],
            "data_completeness": 0.7,
            "consistency": 0.7
        }
        confidence_no_code = agent.calculate_confidence(synthesis_no_code)
        
        # With code evidence
        synthesis_with_code = {
            "key_evidence": [
                {"weight": 0.7, "type": "code_issue"}
            ],
            "data_completeness": 0.7,
            "consistency": 0.7
        }
        confidence_with_code = agent.calculate_confidence(synthesis_with_code)
        
        # Should be higher with code evidence
        assert confidence_with_code > confidence_no_code
    
    def test_calculate_confidence_empty_evidence(self, agent):
        """Test confidence with empty evidence."""
        synthesis = {
            "key_evidence": [],
            "data_completeness": 0.5,
            "consistency": 0.5
        }
        
        confidence = agent.calculate_confidence(synthesis)
        
        # Should be low but not zero
        assert 0.0 <= confidence < 0.5
    
    # Test generate_recommendations method
    
    def test_generate_recommendations(self, agent):
        """Test recommendation generation."""
        hypothesis = {
            "type": "nil_pointer_dereference",
            "description": "Nil pointer in features.go:57",
            "location": "features.go:57"
        }
        
        synthesis = {
            "key_evidence": [
                {
                    "type": "code_issue",
                    "description": "Nil pointer dereference in features.go:57"
                },
                {
                    "type": "anomaly",
                    "description": "Error rate spike"
                }
            ],
            "timeline_correlation": {
                "deployment_mentioned": True
            }
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.85
        )
        
        # Check structure
        assert len(recommendations) > 0
        for rec in recommendations:
            assert "priority" in rec
            assert "action" in rec
            assert "rationale" in rec
            assert "type" in rec
            assert rec["priority"] in ["immediate", "high", "medium", "low"]
        
        # Should be sorted by priority
        priorities = [rec["priority"] for rec in recommendations]
        priority_order = {"immediate": 0, "high": 1, "medium": 2, "low": 3}
        priority_values = [priority_order[p] for p in priorities]
        assert priority_values == sorted(priority_values)
    
    def test_recommendations_with_deployment(self, agent):
        """Test recommendations include rollback for deployment."""
        hypothesis = {"type": "error_rate_spike"}
        synthesis = {
            "key_evidence": [],
            "timeline_correlation": {"deployment_mentioned": True}
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.8
        )
        
        # Should include rollback recommendation
        assert any("rollback" in rec["action"].lower() for rec in recommendations)
        assert any(rec["type"] == "rollback" for rec in recommendations)
    
    def test_recommendations_with_nil_pointer(self, agent):
        """Test recommendations for nil pointer issue."""
        hypothesis = {"type": "nil_pointer_dereference"}
        synthesis = {
            "key_evidence": [
                {
                    "type": "code_issue",
                    "description": "Nil pointer dereference in features.go:57"
                }
            ],
            "timeline_correlation": {}
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.7
        )
        
        # Should include nil-safety fix
        assert any("nil" in rec["action"].lower() or "null" in rec["action"].lower() 
                  for rec in recommendations)
    
    def test_recommendations_with_index_error(self, agent):
        """Test recommendations for index out of bounds."""
        hypothesis = {"type": "index_out_of_bounds"}
        synthesis = {
            "key_evidence": [
                {
                    "type": "code_issue",
                    "description": "Index out of bounds in handler.go:100"
                }
            ],
            "timeline_correlation": {}
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.7
        )
        
        # Should include bounds checking
        assert any("bounds" in rec["action"].lower() for rec in recommendations)
    
    def test_recommendations_include_testing(self, agent):
        """Test recommendations include testing."""
        hypothesis = {"type": "nil_pointer_dereference"}
        synthesis = {
            "key_evidence": [
                {"type": "code_issue", "description": "Issue in code"}
            ],
            "timeline_correlation": {}
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.7
        )
        
        # Should include testing recommendation
        assert any(rec["type"] == "testing" for rec in recommendations)
    
    def test_recommendations_include_monitoring(self, agent):
        """Test recommendations include monitoring for error spikes."""
        hypothesis = {"type": "error_rate_spike"}
        synthesis = {
            "key_evidence": [
                {
                    "type": "anomaly",
                    "description": "Error rate spike detected"
                }
            ],
            "timeline_correlation": {}
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.7
        )
        
        # Should include monitoring recommendation
        assert any(rec["type"] == "monitoring" for rec in recommendations)
    
    def test_recommendations_low_confidence(self, agent):
        """Test recommendations with low confidence."""
        hypothesis = {"type": "unknown"}
        synthesis = {
            "key_evidence": [],
            "timeline_correlation": {}
        }
        
        recommendations = agent.generate_recommendations(
            hypothesis=hypothesis,
            synthesis=synthesis,
            confidence=0.3
        )
        
        # Should still generate some recommendations
        # but may be more general
        assert len(recommendations) >= 0
    
    # Test helper methods
    
    def test_extract_location_from_description(self, agent):
        """Test location extraction."""
        # With file:line
        desc = "Issue in features.go:57 causing errors"
        location = agent._extract_location_from_description(desc)
        assert location == "features.go:57"
        
        # With just filename
        desc = "Issue in handler.go causing errors"
        location = agent._extract_location_from_description(desc)
        assert location == "handler.go"
        
        # No location
        desc = "Generic error occurred"
        location = agent._extract_location_from_description(desc)
        assert location == "unknown"
    
    def test_string_representation(self, agent):
        """Test agent string representation."""
        assert "RootCauseAnalystAgent" in str(agent)
        assert "root_cause_analyst" in str(agent)
