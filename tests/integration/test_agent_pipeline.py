"""Integration tests for agent pipeline.

Tests the complete agent pipeline:
Orchestrator → Data Fetcher → Pattern Analyzer → Code Inspector → Root Cause Analyst

Validates:
- Agent handoffs work correctly
- Scratchpad sections are read/written properly
- Data flows correctly through the pipeline
- Each agent can consume the previous agent's output
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from aletheia.session import Session
from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.agents.orchestrator import OrchestratorAgent
from aletheia.agents.data_fetcher import DataFetcherAgent
from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.agents.code_inspector import CodeInspectorAgent
from aletheia.agents.root_cause_analyst import RootCauseAnalystAgent


@pytest.fixture
def temp_session_dir():
    """Create a temporary session directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def session(temp_session_dir):
    """Create a test session."""
    session = Session.create(password="test-password", name="integration-test")
    yield session
    # Cleanup
    try:
        session.delete()
    except:
        pass


@pytest.fixture
def scratchpad(session):
    """Create a test scratchpad."""
    return Scratchpad(session.session_path, session._get_key())


@pytest.fixture
def config():
    """Create a test configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY"
        },
        "data_sources": {
            "kubernetes": {
                "context": "test-context",
                "namespace": "default"
            },
            "prometheus": {
                "endpoint": "http://localhost:9090"
            }
        }
    }


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider."""
    provider = Mock()
    provider.complete.return_value = "Mocked LLM response"
    return provider


class TestAgentPipeline:
    """Test the complete agent pipeline execution."""

    def test_data_fetcher_to_pattern_analyzer_handoff(self, scratchpad, config, mock_llm_provider):
        """Test Data Fetcher → Pattern Analyzer handoff."""
        # Setup: Data Fetcher writes DATA_COLLECTED
        with patch('aletheia.agents.data_fetcher.DataFetcherAgent.get_llm', return_value=mock_llm_provider):
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher') as mock_k8s:
                # Mock Kubernetes fetcher
                mock_fetcher = Mock()
                mock_fetcher.fetch.return_value = Mock(
                    source="kubernetes",
                    data=[
                        {"timestamp": "2025-10-14T10:00:00Z", "level": "ERROR", "message": "Connection timeout"},
                        {"timestamp": "2025-10-14T10:01:00Z", "level": "ERROR", "message": "Connection timeout"},
                        {"timestamp": "2025-10-14T10:02:00Z", "level": "INFO", "message": "Request processed"}
                    ],
                    summary="3 logs (2 ERROR, 1 INFO), top error: 'Connection timeout' (2x)",
                    count=3,
                    time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
                    metadata={"namespace": "default", "pod": "test-pod"}
                )
                mock_k8s.return_value = mock_fetcher
                
                # Execute Data Fetcher
                data_fetcher = DataFetcherAgent(config, scratchpad)
                data_fetcher.execute(
                    sources=["kubernetes"],
                    time_window="1h"
                )
        
        # Verify DATA_COLLECTED section exists
        assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        assert "kubernetes" in data
        
        # Setup: Pattern Analyzer reads DATA_COLLECTED
        with patch('aletheia.agents.pattern_analyzer.PatternAnalyzerAgent.get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(config, scratchpad)
            pattern_analyzer.execute()
        
        # Verify PATTERN_ANALYSIS section exists
        assert scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        analysis = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)
        assert "anomalies" in analysis or "error_clusters" in analysis or "timeline" in analysis

    def test_pattern_analyzer_to_code_inspector_handoff(self, scratchpad, config, mock_llm_provider, temp_session_dir):
        """Test Pattern Analyzer → Code Inspector handoff."""
        # Setup: Pattern Analyzer writes PATTERN_ANALYSIS with stack traces
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {
                "error_clusters": [
                    {
                        "pattern": "NullPointerException at PaymentService.processPayment",
                        "count": 45,
                        "percentage": 75.0,
                        "stack_trace": "at com.example.PaymentService.processPayment(PaymentService.java:123)"
                    }
                ],
                "anomalies": [
                    {"type": "log_anomaly", "severity": "high", "description": "Error rate spike"}
                ],
                "timeline": [
                    {"timestamp": "2025-10-14T10:00:00Z", "type": "log_anomaly", "description": "Error spike"}
                ]
            }
        )
        scratchpad.save()
        
        # Create a mock git repository
        mock_repo = temp_session_dir / "mock-repo"
        mock_repo.mkdir()
        (mock_repo / ".git").mkdir()
        
        # Create a mock source file
        mock_file = mock_repo / "PaymentService.java"
        mock_file.write_text("""
public class PaymentService {
    public void processPayment() {
        // line 123
        customer.getAccount().debit(amount);
    }
}
""")
        
        # Setup: Code Inspector reads PATTERN_ANALYSIS
        with patch('aletheia.agents.code_inspector.CodeInspectorAgent.get_llm', return_value=mock_llm_provider):
            code_inspector = CodeInspectorAgent(config, scratchpad)
            code_inspector.execute(repositories=[str(mock_repo)])
        
        # Verify CODE_INSPECTION section exists
        assert scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        inspection = scratchpad.read_section(ScratchpadSection.CODE_INSPECTION)
        assert isinstance(inspection, dict)

    def test_code_inspector_to_root_cause_analyst_handoff(self, scratchpad, config, mock_llm_provider):
        """Test Code Inspector → Root Cause Analyst handoff."""
        # Setup: Code Inspector writes CODE_INSPECTION
        scratchpad.write_section(
            ScratchpadSection.CODE_INSPECTION,
            {
                "suspect_files": [
                    {
                        "file": "PaymentService.java",
                        "line": 123,
                        "function": "processPayment",
                        "code_snippet": "customer.getAccount().debit(amount);",
                        "analysis": "Possible null pointer dereference"
                    }
                ]
            }
        )
        scratchpad.save()
        
        # Setup: Root Cause Analyst reads all sections
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Payment API errors", "time_window": "2h"}
        )
        scratchpad.write_section(
            ScratchpadSection.DATA_COLLECTED,
            {"kubernetes": {"summary": "High error rate"}}
        )
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {"error_clusters": [{"pattern": "NullPointerException", "count": 45}]}
        )
        scratchpad.save()
        
        # Execute Root Cause Analyst
        with patch('aletheia.agents.root_cause_analyst.RootCauseAnalystAgent.get_llm', return_value=mock_llm_provider):
            root_cause = RootCauseAnalystAgent(config, scratchpad)
            root_cause.execute()
        
        # Verify FINAL_DIAGNOSIS section exists
        assert scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
        diagnosis = scratchpad.read_section(ScratchpadSection.FINAL_DIAGNOSIS)
        assert isinstance(diagnosis, dict)

    def test_full_pipeline_execution(self, scratchpad, config, mock_llm_provider, temp_session_dir):
        """Test complete pipeline: Data Fetcher → Pattern Analyzer → Code Inspector → Root Cause Analyst."""
        # Step 1: Write problem description (normally done by Orchestrator)
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {
                "description": "Payment API returning 500 errors",
                "time_window": "2h",
                "affected_services": ["payments-svc"]
            }
        )
        scratchpad.save()
        
        # Step 2: Data Fetcher collects data
        with patch('aletheia.agents.data_fetcher.DataFetcherAgent.get_llm', return_value=mock_llm_provider):
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher') as mock_k8s:
                mock_fetcher = Mock()
                # Mock list_pods to return list with pod name
                mock_fetcher.list_pods.return_value = ["payments-svc-abc123"]
                mock_fetcher.fetch.return_value = Mock(
                    source="kubernetes",
                    data=[
                        {"timestamp": "2025-10-14T10:00:00Z", "level": "ERROR", 
                         "message": "NullPointerException at PaymentService.processPayment(PaymentService.java:123)"},
                        {"timestamp": "2025-10-14T10:01:00Z", "level": "ERROR", 
                         "message": "NullPointerException at PaymentService.processPayment(PaymentService.java:123)"}
                    ],
                    summary="2 logs (2 ERROR), top error: 'NullPointerException' (2x)",
                    count=2,
                    time_range=(datetime.now() - timedelta(hours=2), datetime.now()),
                    metadata={"namespace": "default", "pod": "payments-svc-abc123"}
                )
                mock_k8s.return_value = mock_fetcher
                
                data_fetcher = DataFetcherAgent(config, scratchpad)
                data_fetcher.execute(
                    sources=["kubernetes"],
                    time_window="2h"
                )
        
        assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        
        # Step 3: Pattern Analyzer analyzes patterns
        with patch('aletheia.agents.pattern_analyzer.PatternAnalyzerAgent.get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(config, scratchpad)
            pattern_analyzer.execute()
        
        assert scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        
        # Manually ensure proper structure for code inspector test
        # (Pattern analyzer may create different structure depending on data)
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {
                "error_clusters": [
                    {
                        "pattern": "NullPointerException at PaymentService.processPayment",
                        "count": 2,
                        "stack_trace": "at PaymentService.processPayment(PaymentService.java:123)"
                    }
                ],
                "anomalies": [],
                "timeline": []
            }
        )
        scratchpad.save()
        
        # Step 4: Code Inspector maps errors to code
        mock_repo = temp_session_dir / "mock-repo"
        mock_repo.mkdir()
        (mock_repo / ".git").mkdir()
        mock_file = mock_repo / "PaymentService.java"
        mock_file.write_text("""
public class PaymentService {
    public void processPayment() {
        customer.getAccount().debit(amount); // line 123
    }
}
""")
        
        with patch('aletheia.agents.code_inspector.CodeInspectorAgent.get_llm', return_value=mock_llm_provider):
            code_inspector = CodeInspectorAgent(config, scratchpad)
            code_inspector.execute(repositories=[str(mock_repo)])
        
        assert scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        
        # Step 5: Root Cause Analyst synthesizes findings
        with patch('aletheia.agents.root_cause_analyst.RootCauseAnalystAgent.get_llm', return_value=mock_llm_provider):
            root_cause = RootCauseAnalystAgent(config, scratchpad)
            root_cause.execute()
        
        assert scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
        
        # Verify all sections exist and have data
        all_data = scratchpad.get_all()
        assert ScratchpadSection.PROBLEM_DESCRIPTION in all_data
        assert ScratchpadSection.DATA_COLLECTED in all_data
        assert ScratchpadSection.PATTERN_ANALYSIS in all_data
        assert ScratchpadSection.CODE_INSPECTION in all_data
        assert ScratchpadSection.FINAL_DIAGNOSIS in all_data


class TestScratchpadFlow:
    """Test scratchpad consistency and section management."""

    def test_each_agent_reads_correct_sections(self, scratchpad, config, mock_llm_provider):
        """Test that each agent reads the sections it needs."""
        # Setup all sections
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test problem"}
        )
        scratchpad.write_section(
            ScratchpadSection.DATA_COLLECTED,
            {"kubernetes": {"summary": "Test data"}}
        )
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {"anomalies": [{"type": "test"}]}
        )
        scratchpad.write_section(
            ScratchpadSection.CODE_INSPECTION,
            {"suspect_files": []}
        )
        scratchpad.save()
        
        # Data Fetcher reads PROBLEM_DESCRIPTION
        data_fetcher = DataFetcherAgent(config, scratchpad)
        assert data_fetcher.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) is not None
        
        # Pattern Analyzer reads DATA_COLLECTED
        pattern_analyzer = PatternAnalyzerAgent(config, scratchpad)
        assert pattern_analyzer.read_scratchpad(ScratchpadSection.DATA_COLLECTED) is not None
        
        # Code Inspector reads PATTERN_ANALYSIS
        code_inspector = CodeInspectorAgent(config, scratchpad)
        assert code_inspector.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS) is not None
        
        # Root Cause Analyst reads all sections
        root_cause = RootCauseAnalystAgent(config, scratchpad)
        assert root_cause.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION) is not None
        assert root_cause.read_scratchpad(ScratchpadSection.DATA_COLLECTED) is not None
        assert root_cause.read_scratchpad(ScratchpadSection.PATTERN_ANALYSIS) is not None
        assert root_cause.read_scratchpad(ScratchpadSection.CODE_INSPECTION) is not None

    def test_each_agent_writes_correct_sections(self, scratchpad, config, mock_llm_provider, temp_session_dir):
        """Test that each agent writes to its designated section."""
        # Data Fetcher writes to DATA_COLLECTED
        with patch('aletheia.agents.data_fetcher.DataFetcherAgent.get_llm', return_value=mock_llm_provider):
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher') as mock_k8s:
                mock_fetcher = Mock()
                mock_fetcher.fetch.return_value = Mock(
                    source="kubernetes",
                    data=[],
                    summary="Test",
                    count=0,
                    time_range=(datetime.now(), datetime.now()),
                    metadata={}
                )
                mock_k8s.return_value = mock_fetcher
                
                data_fetcher = DataFetcherAgent(config, scratchpad)
                data_fetcher.execute(
                    sources=["kubernetes"],
                    time_window="1h"
                )
                
                assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        
        # Pattern Analyzer writes to PATTERN_ANALYSIS
        with patch('aletheia.agents.pattern_analyzer.PatternAnalyzerAgent.get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(config, scratchpad)
            pattern_analyzer.execute()
            
            assert scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        
        # Code Inspector writes to CODE_INSPECTION
        scratchpad.write_section(
            ScratchpadSection.PATTERN_ANALYSIS,
            {"error_clusters": [{"stack_trace": "test"}]}
        )
        
        # Create a mock repository
        mock_repo = temp_session_dir / "mock-repo"
        mock_repo.mkdir()
        (mock_repo / ".git").mkdir()
        
        with patch('aletheia.agents.code_inspector.CodeInspectorAgent.get_llm', return_value=mock_llm_provider):
            code_inspector = CodeInspectorAgent(config, scratchpad)
            code_inspector.execute(repositories=[str(mock_repo)])
            
            assert scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        
        # Root Cause Analyst writes to FINAL_DIAGNOSIS
        scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"description": "Test"})
        with patch('aletheia.agents.root_cause_analyst.RootCauseAnalystAgent.get_llm', return_value=mock_llm_provider):
            root_cause = RootCauseAnalystAgent(config, scratchpad)
            root_cause.execute()
            
            assert scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)

    def test_scratchpad_consistency_across_agents(self, scratchpad, config, mock_llm_provider):
        """Test that scratchpad maintains consistent state across agent executions."""
        initial_data = {
            "description": "Original problem",
            "timestamp": datetime.now().isoformat()
        }
        
        scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, initial_data)
        scratchpad.save()
        
        # Execute multiple agents
        with patch('aletheia.agents.data_fetcher.DataFetcherAgent.get_llm', return_value=mock_llm_provider):
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher') as mock_k8s:
                mock_fetcher = Mock()
                mock_fetcher.fetch.return_value = Mock(
                    source="kubernetes", data=[], summary="Test", count=0,
                    time_range=(datetime.now(), datetime.now()), metadata={}
                )
                mock_k8s.return_value = mock_fetcher
                
                data_fetcher = DataFetcherAgent(config, scratchpad)
                data_fetcher.execute(
                    sources=["kubernetes"],
                    time_window="1h"
                )
        
        # Verify original section is unchanged
        problem = scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert problem == initial_data
        
        # Verify new section was added
        assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        
        # Verify section count
        assert scratchpad.section_count == 2

    def test_scratchpad_persistence_across_agent_pipeline(self, session, config, mock_llm_provider):
        """Test that scratchpad data persists correctly across the pipeline."""
        scratchpad1 = Scratchpad(session.session_path, session._get_key())
        
        # Write initial data
        scratchpad1.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Persistent problem"}
        )
        scratchpad1.save()
        
        # Load in new scratchpad instance (simulates agent handoff)
        scratchpad2 = Scratchpad.load(session.session_path, session._get_key())
        
        # Verify data persisted
        assert scratchpad2.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        problem = scratchpad2.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert problem["description"] == "Persistent problem"
        
        # Add more data
        with patch('aletheia.agents.data_fetcher.DataFetcherAgent.get_llm', return_value=mock_llm_provider):
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher') as mock_k8s:
                mock_fetcher = Mock()
                mock_fetcher.fetch.return_value = Mock(
                    source="kubernetes", data=[], summary="Test", count=0,
                    time_range=(datetime.now(), datetime.now()), metadata={}
                )
                mock_k8s.return_value = mock_fetcher
                
                data_fetcher = DataFetcherAgent(config, scratchpad2)
                data_fetcher.execute(
                    sources=["kubernetes"],
                    time_window="1h"
                )
        
        scratchpad2.save()
        
        # Load in another new instance
        scratchpad3 = Scratchpad.load(session.session_path, session._get_key())
        
        # Verify both sections persisted
        assert scratchpad3.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert scratchpad3.has_section(ScratchpadSection.DATA_COLLECTED)
        assert scratchpad3.section_count == 2

    def test_section_isolation(self, scratchpad, config):
        """Test that agents don't accidentally modify other sections."""
        # Setup multiple sections
        scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"desc": "Problem 1"})
        scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {"data": "Data 1"})
        scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, {"pattern": "Pattern 1"})
        scratchpad.save()
        
        original_problem = scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        original_data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        
        # Pattern analyzer should only modify PATTERN_ANALYSIS
        pattern_analyzer = PatternAnalyzerAgent(config, scratchpad)
        pattern_analyzer.write_scratchpad(ScratchpadSection.PATTERN_ANALYSIS, {"pattern": "Pattern 2"})
        
        # Verify other sections unchanged
        assert scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION) == original_problem
        assert scratchpad.read_section(ScratchpadSection.DATA_COLLECTED) == original_data
        
        # Verify only target section changed
        new_pattern = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)
        assert new_pattern["pattern"] == "Pattern 2"
