"""Tests for demo mode functionality."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from aletheia.demo.data import DemoDataProvider
from aletheia.demo.scenario import DEMO_SCENARIOS, DemoScenario
from aletheia.demo.agents import (
    MockDataFetcherAgent,
    MockPatternAnalyzerAgent,
    MockCodeInspectorAgent,
    MockRootCauseAnalystAgent,
    create_mock_agents,
)
from aletheia.demo.orchestrator import DemoOrchestrator
from aletheia.scratchpad import Scratchpad


class TestDemoDataProvider:
    """Test suite for DemoDataProvider."""
    
    def test_initialization(self):
        """Test provider initialization with scenario."""
        provider = DemoDataProvider("payment_service_crash")
        assert provider.scenario == "payment_service_crash"
    
    def test_get_kubernetes_logs_payment_scenario(self):
        """Test getting Kubernetes logs for payment service crash."""
        provider = DemoDataProvider("payment_service_crash")
        logs = provider.get_kubernetes_logs("payment-service", "default", "1h")
        
        assert len(logs) > 0
        assert any(log["level"] == "ERROR" for log in logs)
        assert any(log["level"] == "FATAL" for log in logs)
        assert any("lock" in log["message"].lower() for log in logs)
    
    def test_get_kubernetes_logs_api_scenario(self):
        """Test getting Kubernetes logs for API latency scenario."""
        provider = DemoDataProvider("api_latency_spike")
        logs = provider.get_kubernetes_logs("api-gateway", "default", "2h")
        
        assert len(logs) > 0
        assert any(log["level"] == "ERROR" for log in logs)
        assert any("timeout" in log["message"].lower() for log in logs)
    
    def test_get_prometheus_metrics_payment_scenario(self):
        """Test getting Prometheus metrics for payment service crash."""
        provider = DemoDataProvider("payment_service_crash")
        start = datetime.now() - timedelta(hours=1)
        end = datetime.now()
        
        metrics = provider.get_prometheus_metrics("payment_error_rate", start, end)
        
        assert len(metrics) > 0
        assert any(m["metric"] == "payment_error_rate" for m in metrics)
        assert any(m["metric"] == "goroutine_count" for m in metrics)
    
    def test_get_prometheus_metrics_api_scenario(self):
        """Test getting Prometheus metrics for API latency scenario."""
        provider = DemoDataProvider("api_latency_spike")
        start = datetime.now() - timedelta(hours=2)
        end = datetime.now()
        
        metrics = provider.get_prometheus_metrics("http_timeout_rate", start, end)
        
        assert len(metrics) > 0
        assert any(m["metric"] == "http_request_duration_p95" for m in metrics)
        assert any(m["metric"] == "http_timeout_rate" for m in metrics)
    
    def test_get_git_blame(self):
        """Test getting git blame information."""
        provider = DemoDataProvider("payment_service_crash")
        blame = provider.get_git_blame("payment.go", 45, "/demo/payment-service")
        
        assert "author" in blame
        assert "commit" in blame
        assert "date" in blame
        assert "message" in blame
        assert blame["line"] == 45
    
    def test_get_code_context_payment_scenario(self):
        """Test getting code context for payment scenario."""
        provider = DemoDataProvider("payment_service_crash")
        context = provider.get_code_context("payment.go", 45, 10)
        
        assert "ProcessPayment" in context
        assert "acquireLock" in context
        assert "releaseLock" in context
    
    def test_get_code_context_api_scenario(self):
        """Test getting code context for API scenario."""
        provider = DemoDataProvider("api_latency_spike")
        context = provider.get_code_context("api.go", 78, 10)
        
        assert "HandleAPIRequest" in context
        assert "WithTimeout" in context
        assert "queryDatabase" in context


class TestDemoScenarios:
    """Test suite for demo scenarios."""
    
    def test_scenarios_registry_exists(self):
        """Test that demo scenarios registry exists."""
        assert len(DEMO_SCENARIOS) > 0
    
    def test_payment_service_crash_scenario(self):
        """Test payment service crash scenario structure."""
        scenario = DEMO_SCENARIOS["payment_service_crash"]
        
        assert scenario.id == "payment_service_crash"
        assert scenario.name
        assert scenario.description
        assert scenario.service_name == "payment-service"
        assert scenario.time_window == "1h"
        assert "kubernetes" in scenario.data_sources
        assert scenario.problem_description
        assert scenario.pattern_analysis
        assert scenario.code_inspection
        assert scenario.final_diagnosis
    
    def test_api_latency_spike_scenario(self):
        """Test API latency spike scenario structure."""
        scenario = DEMO_SCENARIOS["api_latency_spike"]
        
        assert scenario.id == "api_latency_spike"
        assert scenario.name
        assert scenario.description
        assert scenario.service_name == "api-gateway"
        assert scenario.time_window == "2h"
        assert scenario.problem_description
        assert scenario.pattern_analysis
        assert scenario.code_inspection
        assert scenario.final_diagnosis
    
    def test_scenario_has_complete_analysis(self):
        """Test that scenarios have complete analysis data."""
        for scenario_id, scenario in DEMO_SCENARIOS.items():
            # Check pattern analysis structure
            assert "anomalies" in scenario.pattern_analysis
            assert "error_clusters" in scenario.pattern_analysis
            assert "timeline" in scenario.pattern_analysis
            
            # Check code inspection structure
            assert "suspect_locations" in scenario.code_inspection
            assert "code_snippets" in scenario.code_inspection
            
            # Check final diagnosis structure
            assert "root_cause" in scenario.final_diagnosis
            assert "hypothesis" in scenario.final_diagnosis
            assert "confidence" in scenario.final_diagnosis
            assert "recommendations" in scenario.final_diagnosis
            
            # Check confidence is reasonable
            assert 0.0 <= scenario.final_diagnosis["confidence"] <= 1.0


@pytest.fixture
def demo_config():
    """Provide a minimal config for demo mode tests."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
        },
    }


@pytest.mark.asyncio
class TestMockAgents:
    """Test suite for mock agents."""
    
    async def test_mock_data_fetcher_execution(self, tmp_path, demo_config):
        """Test mock data fetcher execution."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        scenario = DEMO_SCENARIOS["payment_service_crash"]
        
        agent = MockDataFetcherAgent(demo_config, scratchpad, scenario)
        result = await agent.execute()
        
        assert result["status"] == "success"
        assert "message" in result
        assert scratchpad.has_section("DATA_COLLECTED")
        
        data = scratchpad.read_section("DATA_COLLECTED")
        assert data["service"] == scenario.service_name
    
    async def test_mock_pattern_analyzer_execution(self, tmp_path, demo_config):
        """Test mock pattern analyzer execution."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        scenario = DEMO_SCENARIOS["payment_service_crash"]
        
        agent = MockPatternAnalyzerAgent(demo_config, scratchpad, scenario)
        result = await agent.execute()
        
        assert result["status"] == "success"
        assert "message" in result
        assert scratchpad.has_section("PATTERN_ANALYSIS")
        
        analysis = scratchpad.read_section("PATTERN_ANALYSIS")
        assert "anomalies" in analysis
    
    async def test_mock_code_inspector_execution(self, tmp_path, demo_config):
        """Test mock code inspector execution."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        scenario = DEMO_SCENARIOS["payment_service_crash"]
        
        agent = MockCodeInspectorAgent(demo_config, scratchpad, scenario)
        result = await agent.execute()
        
        assert result["status"] == "success"
        assert "message" in result
        assert scratchpad.has_section("CODE_INSPECTION")
        
        inspection = scratchpad.read_section("CODE_INSPECTION")
        assert "suspect_locations" in inspection
    
    async def test_mock_root_cause_analyst_execution(self, tmp_path, demo_config):
        """Test mock root cause analyst execution."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        scenario = DEMO_SCENARIOS["payment_service_crash"]
        
        agent = MockRootCauseAnalystAgent(demo_config, scratchpad, scenario)
        result = await agent.execute()
        
        assert result["status"] == "success"
        assert "message" in result
        assert scratchpad.has_section("FINAL_DIAGNOSIS")
        
        diagnosis = scratchpad.read_section("FINAL_DIAGNOSIS")
        assert "root_cause" in diagnosis
        assert "confidence" in diagnosis
    
    def test_create_mock_agents(self, tmp_path, demo_config):
        """Test creating all mock agents for a scenario."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        
        agents = create_mock_agents(demo_config, scratchpad, "payment_service_crash")
        
        assert "data_fetcher" in agents
        assert "pattern_analyzer" in agents
        assert "code_inspector" in agents
        assert "root_cause_analyst" in agents
        
        assert isinstance(agents["data_fetcher"], MockDataFetcherAgent)
        assert isinstance(agents["pattern_analyzer"], MockPatternAnalyzerAgent)
        assert isinstance(agents["code_inspector"], MockCodeInspectorAgent)
        assert isinstance(agents["root_cause_analyst"], MockRootCauseAnalystAgent)
    
    def test_create_mock_agents_invalid_scenario(self, tmp_path, demo_config):
        """Test creating mock agents with invalid scenario ID."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        
        with pytest.raises(ValueError, match="Unknown scenario"):
            create_mock_agents(demo_config, scratchpad, "invalid_scenario")


@pytest.mark.asyncio
class TestDemoOrchestrator:
    """Test suite for demo orchestrator."""
    
    def test_orchestrator_initialization(self, tmp_path, demo_config):
        """Test demo orchestrator initialization."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        
        orchestrator = DemoOrchestrator(demo_config, scratchpad, "payment_service_crash")
        
        assert orchestrator.scenario.id == "payment_service_crash"
        assert len(orchestrator.agents) == 4
    
    def test_orchestrator_invalid_scenario(self, tmp_path, demo_config):
        """Test orchestrator initialization with invalid scenario."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        
        with pytest.raises(ValueError, match="Unknown scenario"):
            DemoOrchestrator(demo_config, scratchpad, "invalid_scenario")
    
    async def test_orchestrator_run_investigation_cancelled(self, tmp_path, demo_config):
        """Test demo orchestrator with user cancellation."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        
        orchestrator = DemoOrchestrator(demo_config, scratchpad, "payment_service_crash")
        
        # Mock Confirm.ask to return False (user cancels)
        with patch("aletheia.demo.orchestrator.Confirm.ask", return_value=False):
            result = await orchestrator.run_investigation()
            
            assert result["status"] == "cancelled"
    
    async def test_orchestrator_run_investigation_full_flow(self, tmp_path, demo_config):
        """Test demo orchestrator full investigation flow."""
        scratchpad = Scratchpad(session_dir=tmp_path, encryption_key=b"a" * 32)
        
        orchestrator = DemoOrchestrator(demo_config, scratchpad, "payment_service_crash")
        
        # Mock Confirm.ask to always return True (user proceeds)
        with patch("aletheia.demo.orchestrator.Confirm.ask", return_value=True):
            result = await orchestrator.run_investigation()
            
            assert result["status"] == "completed"
            assert "diagnosis" in result
            
            # Verify all scratchpad sections were written
            assert scratchpad.has_section("DATA_COLLECTED")
            assert scratchpad.has_section("PATTERN_ANALYSIS")
            assert scratchpad.has_section("CODE_INSPECTION")
            assert scratchpad.has_section("FINAL_DIAGNOSIS")
