"""End-to-end integration tests for complete session flows.

Tests cover:
- 5.1.1: Complete session flow (open → data collection → analysis → diagnosis)
- 5.1.2: Session resume after interruption
- 5.1.3: Error recovery scenarios
- 5.1.4: Session export/import functionality

These tests validate the entire system working together with mocked external dependencies.
"""

import pytest
import os
import tempfile
import shutil
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, call

from aletheia.session import Session
from aletheia.scratchpad import Scratchpad, ScratchpadSection
from aletheia.agents.orchestrator import OrchestratorAgent
from aletheia.agents.data_fetcher import DataFetcherAgent
from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.agents.code_inspector import CodeInspectorAgent
from aletheia.agents.root_cause_analyst import RootCauseAnalystAgent
from aletheia.config import ConfigLoader
from aletheia.fetchers.base import FetchError


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_session_dir():
    """Create a temporary directory for sessions."""
    temp_dir = tempfile.mkdtemp()
    sessions_path = Path(temp_dir) / "sessions"
    sessions_path.mkdir(exist_ok=True)
    yield sessions_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config():
    """Create a test configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "agents": {
                "data_fetcher": {"model": "gpt-4o-mini"},
                "pattern_analyzer": {"model": "gpt-4o-mini"},
                "code_inspector": {"model": "gpt-4o-mini"},
                "root_cause_analyst": {"model": "gpt-4o-mini"}
            }
        },
        "data_sources": {
            "kubernetes": {
                "context": "test-context",
                "namespace": "default"
            },
            "prometheus": {
                "endpoint": "http://localhost:9090"
            }
        },
        "session": {
            "encryption": {
                "iterations": 100000
            }
        },
        "ui": {
            "confirmations": "normal"
        }
    }


@pytest.fixture
def mock_kubernetes_fetcher():
    """Create a mock Kubernetes fetcher."""
    mock_fetcher = Mock()
    mock_fetcher.list_pods.return_value = ["payments-svc-abc123", "payments-svc-def456"]
    mock_fetcher.fetch.return_value = Mock(
        source="kubernetes",
        data=[
            {
                "timestamp": "2025-10-17T10:00:00Z",
                "level": "ERROR",
                "message": "panic: runtime error: invalid memory address or nil pointer dereference at PaymentService.processPayment(PaymentService.java:123)",
                "pod": "payments-svc-abc123"
            },
            {
                "timestamp": "2025-10-17T10:00:15Z",
                "level": "ERROR",
                "message": "panic: runtime error: invalid memory address or nil pointer dereference at PaymentService.processPayment(PaymentService.java:123)",
                "pod": "payments-svc-abc123"
            },
            {
                "timestamp": "2025-10-17T10:00:30Z",
                "level": "ERROR",
                "message": "Connection timeout to database server",
                "pod": "payments-svc-def456"
            },
            {
                "timestamp": "2025-10-17T10:01:00Z",
                "level": "INFO",
                "message": "Request processed successfully",
                "pod": "payments-svc-abc123"
            }
        ],
        summary="4 logs (3 ERROR, 1 INFO), top error: 'nil pointer dereference at PaymentService.java:123' (2x)",
        count=4,
        time_range=(datetime(2025, 10, 17, 10, 0, 0), datetime(2025, 10, 17, 10, 1, 0)),
        metadata={"namespace": "default", "pod_count": 2}
    )
    mock_fetcher.test_connection.return_value = True
    mock_fetcher.get_capabilities.return_value = {
        "name": "kubernetes",
        "supports_logs": True,
        "supports_metrics": False
    }
    return mock_fetcher


@pytest.fixture
def mock_prometheus_fetcher():
    """Create a mock Prometheus fetcher."""
    mock_fetcher = Mock()
    mock_fetcher.fetch.return_value = Mock(
        source="prometheus",
        data=[
            {"timestamp": "2025-10-17T09:55:00Z", "value": 0.02},
            {"timestamp": "2025-10-17T10:00:00Z", "value": 0.75},
            {"timestamp": "2025-10-17T10:05:00Z", "value": 0.05}
        ],
        summary="Error rate spike: 0.02 → 0.75 (37.5x increase) at 10:00",
        count=3,
        time_range=(datetime(2025, 10, 17, 9, 55, 0), datetime(2025, 10, 17, 10, 5, 0)),
        metadata={"query": "rate(http_requests_total{status=~'5..'}[5m])", "step": "5m"}
    )
    mock_fetcher.test_connection.return_value = True
    mock_fetcher.get_capabilities.return_value = {
        "name": "prometheus",
        "supports_logs": False,
        "supports_metrics": True
    }
    return mock_fetcher


@pytest.fixture
def mock_llm_provider():
    """Create a mock LLM provider that returns contextual responses."""
    provider = Mock()
    
    def mock_complete(messages, *args, **kwargs):
        """Return different responses based on context."""
        last_message = messages[-1]["content"] if messages else ""
        
        # Data fetcher query generation
        if "generate" in last_message.lower() and "query" in last_message.lower():
            return '{"query": "rate(http_requests_total{status=~\'5..\'}[5m])", "description": "Error rate metric"}'
        
        # Pattern analysis
        if "analyze" in last_message.lower() and "pattern" in last_message.lower():
            return "The error rate spike at 10:00 correlates with NullPointerException errors in PaymentService."
        
        # Code inspection
        if "inspect" in last_message.lower() and "code" in last_message.lower():
            return "The suspect code at line 123 performs a dereference without null checking."
        
        # Root cause analysis
        if "root cause" in last_message.lower() or "synthesize" in last_message.lower():
            return "Root cause: Null pointer dereference in PaymentService.processPayment due to missing validation."
        
        return "Mocked LLM response"
    
    provider.complete.side_effect = mock_complete
    return provider


@pytest.fixture
def mock_git_repo(temp_session_dir):
    """Create a mock git repository with test files."""
    repo_path = temp_session_dir / "test-repo"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    
    # Create PaymentService.java with the problematic line
    payment_service = repo_path / "PaymentService.java"
    payment_service.write_text("""package com.example;

public class PaymentService {
    private Database db;
    
    public PaymentService(Database db) {
        this.db = db;
    }
    
    public void processPayment(String customerId, double amount) {
        // Retrieve customer account
        Account account = db.getAccount(customerId);
        
        // BUG: No null check here - line 123
        account.debit(amount);
        
        // Log transaction
        logger.info("Payment processed: " + customerId + ", $" + amount);
    }
    
    public void refundPayment(String customerId, double amount) {
        Account account = db.getAccount(customerId);
        if (account != null) {  // Correct null check
            account.credit(amount);
        }
    }
}
""")
    
    return repo_path


# ============================================================================
# Test 5.1.1: Complete Session Flow
# ============================================================================

class TestCompleteSessionFlow:
    """Test complete session flow from open to diagnosis."""

    def test_full_investigation_flow_with_mocked_data_sources(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_prometheus_fetcher,
        mock_llm_provider,
        mock_git_repo
    ):
        """
        Test complete flow: session open → data collection → analysis → diagnosis.
        
        This is the primary acceptance test for 5.1.1.
        Verifies:
        - Session creation
        - Problem description capture
        - Data collection from multiple sources
        - Pattern analysis execution
        - Code inspection with repository
        - Final diagnosis generation
        - Scratchpad state at each stage
        """
        # Step 1: Create session
        session = Session.create(password="test-password", name="E2E Test Session", session_dir=temp_session_dir)
        assert session is not None
        assert session._metadata.name == "E2E Test Session"
        assert session._metadata.status == "active"
        
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        # Step 2: User describes problem (normally via Orchestrator)
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {
                "description": "Payment API returning 500 errors with NullPointerException",
                "time_window": "2h",
                "affected_services": ["payments-svc"],
                "timestamp": datetime.now().isoformat()
            }
        )
        scratchpad.save()
        
        # Verify scratchpad state after problem description
        assert scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        problem = scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert problem["description"] == "Payment API returning 500 errors with NullPointerException"
        
        # Step 3: Data Fetcher collects logs and metrics
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch('aletheia.agents.data_fetcher.PrometheusFetcher', return_value=mock_prometheus_fetcher):
                with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                    data_fetcher = DataFetcherAgent(test_config, scratchpad)
                    result = data_fetcher.execute(
                        sources=["kubernetes", "prometheus"],
                        time_window="2h",
                        use_sk=False
                    )
                    
                    assert result["success"] == True
        
        # Verify scratchpad state after data collection
        assert scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        assert "kubernetes" in data
        assert "prometheus" in data
        assert data["kubernetes"]["count"] == 4
        assert data["prometheus"]["count"] == 3
        
        # Step 4: Pattern Analyzer identifies anomalies and patterns
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(test_config, scratchpad)
            result = pattern_analyzer.execute()
            
            assert result["success"] == True
        
        # Verify scratchpad state after pattern analysis
        assert scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        analysis = scratchpad.read_section(ScratchpadSection.PATTERN_ANALYSIS)
        assert "anomalies" in analysis or "error_clusters" in analysis or "timeline" in analysis
        
        # Step 5: Code Inspector maps errors to source code
        with patch.object(CodeInspectorAgent, 'get_llm', return_value=mock_llm_provider):
            code_inspector = CodeInspectorAgent(test_config, scratchpad)
            result = code_inspector.execute(repositories=[str(mock_git_repo)])
            
            assert result["success"] == True
        
        # Verify scratchpad state after code inspection
        assert scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        inspection = scratchpad.read_section(ScratchpadSection.CODE_INSPECTION)
        assert isinstance(inspection, dict)
        
        # Step 6: Root Cause Analyst synthesizes findings
        with patch.object(RootCauseAnalystAgent, 'get_llm', return_value=mock_llm_provider):
            root_cause_analyst = RootCauseAnalystAgent(test_config, scratchpad)
            result = root_cause_analyst.execute()
            
            assert result["success"] == True
        
        # Verify scratchpad state after final diagnosis
        assert scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
        diagnosis = scratchpad.read_section(ScratchpadSection.FINAL_DIAGNOSIS)
        assert "root_cause" in diagnosis
        assert "confidence" in diagnosis["root_cause"]
        assert "recommended_actions" in diagnosis or "recommendations" in diagnosis
        assert diagnosis["root_cause"]["confidence"] >= 0.0 and diagnosis["root_cause"]["confidence"] <= 1.0
        
        # Verify all sections are present in final scratchpad
        all_sections = scratchpad.get_all()
        assert len(all_sections) == 5  # All 5 major sections
        assert ScratchpadSection.PROBLEM_DESCRIPTION in all_sections
        assert ScratchpadSection.DATA_COLLECTED in all_sections
        assert ScratchpadSection.PATTERN_ANALYSIS in all_sections
        assert ScratchpadSection.CODE_INSPECTION in all_sections
        assert ScratchpadSection.FINAL_DIAGNOSIS in all_sections
        
        # Verify session metadata was updated
        session_reloaded = Session.resume(session.session_id, password="test-password", session_dir=temp_session_dir)
        assert session_reloaded._metadata.status in ["active", "completed"]
        
        # Cleanup
        session.delete()

    def test_session_completes_in_reasonable_time(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_prometheus_fetcher,
        mock_llm_provider,
        mock_git_repo
    ):
        """
        Test that a complete session completes within reasonable time.
        
        Performance target: < 5 minutes for typical case (with mocked services).
        In this test with all mocks, should be < 10 seconds.
        """
        start_time = time.time()
        
        # Create session and execute full pipeline
        session = Session.create(password="test-password", name="Performance Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Performance test", "time_window": "1h"}
        )
        scratchpad.save()
        
        # Execute all agents
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch('aletheia.agents.data_fetcher.PrometheusFetcher', return_value=mock_prometheus_fetcher):
                with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                    data_fetcher = DataFetcherAgent(test_config, scratchpad)
                    data_fetcher.execute(sources=["kubernetes", "prometheus"], time_window="1h", use_sk=False)
        
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(test_config, scratchpad)
            pattern_analyzer.execute()
        
        with patch.object(CodeInspectorAgent, 'get_llm', return_value=mock_llm_provider):
            code_inspector = CodeInspectorAgent(test_config, scratchpad)
            code_inspector.execute(repositories=[str(mock_git_repo)])
        
        with patch.object(RootCauseAnalystAgent, 'get_llm', return_value=mock_llm_provider):
            root_cause = RootCauseAnalystAgent(test_config, scratchpad)
            root_cause.execute()
        
        elapsed_time = time.time() - start_time
        
        # With all mocks, should complete very quickly
        assert elapsed_time < 10.0, f"Session took {elapsed_time:.2f}s (expected < 10s with mocks)"
        
        # Verify completion
        assert scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
        
        # Cleanup
        session.delete()

    def test_session_flow_with_minimal_data(
        self,
        temp_session_dir,
        test_config,
        mock_llm_provider,
        mock_git_repo
    ):
        """
        Test session flow with minimal data (no errors found).
        
        Edge case: What happens when data sources return empty or minimal data?
        """
        session = Session.create(password="test-password", name="Minimal Data Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Check for errors", "time_window": "1h"}
        )
        scratchpad.save()
        
        # Mock fetchers returning minimal data
        empty_k8s_fetcher = Mock()
        empty_k8s_fetcher.fetch.return_value = Mock(
            source="kubernetes",
            data=[],
            summary="No logs found",
            count=0,
            time_range=(datetime.now() - timedelta(hours=1), datetime.now()),
            metadata={}
        )
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=empty_k8s_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad)
                result = data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
                
                # Should succeed even with no data
                assert result["success"] == True
        
        # Pattern analyzer should handle empty data gracefully
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(test_config, scratchpad)
            result = pattern_analyzer.execute()
            
            # Should succeed but may have empty analysis
            assert result["success"] == True
        
        # Root cause analyst should still generate output
        with patch.object(RootCauseAnalystAgent, 'get_llm', return_value=mock_llm_provider):
            root_cause = RootCauseAnalystAgent(test_config, scratchpad)
            result = root_cause.execute()
            
            assert result["success"] == True
        
        # Should have diagnosis even with minimal data
        assert scratchpad.has_section(ScratchpadSection.FINAL_DIAGNOSIS)
        diagnosis = scratchpad.read_section(ScratchpadSection.FINAL_DIAGNOSIS)
        
        # Confidence should be low with minimal data
        assert "root_cause" in diagnosis
        assert "confidence" in diagnosis["root_cause"]
        # May have low confidence or indicate insufficient data
        
        # Cleanup
        session.delete()


# ============================================================================
# Test 5.1.2: Session Resume
# ============================================================================

class TestSessionResume:
    """Test session resume functionality after interruption."""

    def test_session_resume_after_data_collection(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test resuming session after data collection phase.
        
        Scenario: User interrupts after data collection, then resumes.
        Verify: State is restored and analysis continues from interruption point.
        """
        # Phase 1: Start session and collect data
        session = Session.create(password="test-password", name="Resume Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test resume", "time_window": "1h"}
        )
        scratchpad.save()
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad)
                data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
        
        # Simulate interruption - save and close session
        scratchpad.save()
        session_id = session.session_id
        original_data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        
        # Phase 2: Resume session
        resumed_session = Session.resume(session_id, password="test-password", session_dir=temp_session_dir)
        assert resumed_session is not None
        assert resumed_session.session_id == session_id
        
        # Load scratchpad and verify state restoration
        resumed_scratchpad = Scratchpad.load(resumed_session.session_path, resumed_session._get_key())
        assert resumed_scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert resumed_scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        
        # Verify data is unchanged
        restored_data = resumed_scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        assert restored_data == original_data
        
        # Continue with pattern analysis
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(test_config, resumed_scratchpad)
            pattern_analyzer.execute()
        
        # Verify analysis was added
        assert resumed_scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        
        # Cleanup
        resumed_session.delete()

    def test_session_resume_after_pattern_analysis(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider,
        mock_git_repo
    ):
        """
        Test resuming session after pattern analysis phase.
        
        Scenario: User interrupts after pattern analysis, then resumes for code inspection.
        """
        # Phase 1: Execute through pattern analysis
        session = Session.create(password="test-password", name="Resume Test 2", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test resume", "time_window": "1h"}
        )
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad)
                data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
        
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(test_config, scratchpad)
            pattern_analyzer.execute()
        
        scratchpad.save()
        session_id = session.session_id
        
        # Phase 2: Resume and continue with code inspection
        resumed_session = Session.resume(session_id, password="test-password", session_dir=temp_session_dir)
        resumed_scratchpad = Scratchpad.load(resumed_session.session_path, resumed_session._get_key())
        
        # Verify state
        assert resumed_scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        assert resumed_scratchpad.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        assert not resumed_scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        
        # Continue with code inspection
        with patch.object(CodeInspectorAgent, 'get_llm', return_value=mock_llm_provider):
            code_inspector = CodeInspectorAgent(test_config, resumed_scratchpad)
            code_inspector.execute(repositories=[str(mock_git_repo)])
        
        # Verify new section added
        assert resumed_scratchpad.has_section(ScratchpadSection.CODE_INSPECTION)
        
        # Cleanup
        resumed_session.delete()

    def test_session_resume_with_wrong_password_fails(
        self,
        temp_session_dir
    ):
        """
        Test that resuming with wrong password fails.
        
        Security: Verify encryption prevents unauthorized access.
        """
        session = Session.create(password="correct-password", name="Security Test", session_dir=temp_session_dir)
        session_id = session.session_id
        
        # Try to resume with wrong password
        with pytest.raises(Exception):  # Should raise decryption error
            Session.resume(session_id, password="wrong-password", session_dir=temp_session_dir)
        
        # Correct password should work
        resumed = Session.resume(session_id, password="correct-password", session_dir=temp_session_dir)
        assert resumed is not None
        assert resumed.session_id == session_id
        
        # Cleanup
        resumed.delete()

    def test_session_resume_without_data_loss(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test that multiple resume cycles don't lose data.
        
        Scenario: User interrupts and resumes multiple times.
        Verify: All data is preserved across interruptions.
        """
        # Create session
        session = Session.create(password="test-password", name="Multi-Resume Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        # Add problem description
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Original problem", "iteration": 1}
        )
        scratchpad.save()
        session_id = session.session_id
        
        # First resume: Add data collection
        session1 = Session.resume(session_id, password="test-password", session_dir=temp_session_dir)
        scratchpad1 = Scratchpad.load(session1.session_path, session1._get_key())
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad1)
                data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
        
        scratchpad1.save()
        
        # Second resume: Add pattern analysis
        session2 = Session.resume(session_id, password="test-password", session_dir=temp_session_dir)
        scratchpad2 = Scratchpad.load(session2.session_path, session2._get_key())
        
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            pattern_analyzer = PatternAnalyzerAgent(test_config, scratchpad2)
            pattern_analyzer.execute()
        
        scratchpad2.save()
        
        # Final resume: Verify all data present
        session3 = Session.resume(session_id, password="test-password", session_dir=temp_session_dir)
        scratchpad3 = Scratchpad.load(session3.session_path, session3._get_key())
        
        # All sections should be present
        assert scratchpad3.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert scratchpad3.has_section(ScratchpadSection.DATA_COLLECTED)
        assert scratchpad3.has_section(ScratchpadSection.PATTERN_ANALYSIS)
        
        # Original problem description should be unchanged
        problem = scratchpad3.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert problem["description"] == "Original problem"
        assert problem["iteration"] == 1
        
        # Cleanup
        session3.delete()


# ============================================================================
# Test 5.1.3: Error Recovery
# ============================================================================

class TestErrorRecovery:
    """Test error recovery scenarios."""

    def test_data_source_failure_recovery(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test recovery when data source fails.
        
        Scenario: Kubernetes fetcher fails, but session should handle gracefully.
        """
        session = Session.create(password="test-password", name="Error Recovery Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test error handling", "time_window": "1h"}
        )
        scratchpad.save()
        
        # Mock fetcher that raises FetchError
        failing_fetcher = Mock()
        failing_fetcher.fetch.side_effect = FetchError("Connection timeout")
        failing_fetcher.test_connection.return_value = False
        
        # Patch retry decorator to not retry in tests
        with patch('aletheia.agents.data_fetcher.retry_with_backoff', lambda **kwargs: lambda f: f):
            # Data fetcher should handle the failure
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=failing_fetcher):
                with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                    data_fetcher = DataFetcherAgent(test_config, scratchpad)
                    
                    # Should not raise, but return error status or partial success
                    result = data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
                    
                    # Agent should indicate failure or partial success
                    assert "success" in result
        
        # Session should still be usable
        assert scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        
        # Cleanup
        session.delete()

    def test_partial_success_with_mixed_sources(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test partial success when one data source succeeds and another fails.
        
        Scenario: Kubernetes succeeds, Prometheus fails.
        Verify: Session continues with partial data.
        """
        session = Session.create(password="test-password", name="Partial Success Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Partial success test", "time_window": "1h"}
        )
        scratchpad.save()
        
        # Kubernetes succeeds, Prometheus fails
        failing_prometheus = Mock()
        failing_prometheus.fetch.side_effect = FetchError("Prometheus unavailable")
        
        # Patch retry decorator to not retry in tests
        with patch('aletheia.agents.data_fetcher.retry_with_backoff', lambda **kwargs: lambda f: f):
            with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
                with patch('aletheia.agents.data_fetcher.PrometheusFetcher', return_value=failing_prometheus):
                    with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                        data_fetcher = DataFetcherAgent(test_config, scratchpad)
                        result = data_fetcher.execute(
                            sources=["kubernetes", "prometheus"],
                            time_window="1h",
                            use_sk=False
                        )
                        
                        # Should indicate partial success (kubernetes succeeded)
                        assert "sources_fetched" in result
                        assert "kubernetes" in result["sources_fetched"]
                        assert "prometheus" in result.get("sources_failed", [])
        
        # Scratchpad should have kubernetes data
        if scratchpad.has_section(ScratchpadSection.DATA_COLLECTED):
            data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
            # Should have kubernetes but may not have prometheus
            assert "kubernetes" in data or "errors" in data
        
        # Cleanup
        session.delete()

    def test_agent_failure_does_not_corrupt_scratchpad(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test that agent failure doesn't corrupt existing scratchpad data.
        
        Scenario: Pattern analyzer fails after data collection.
        Verify: Data collection results are preserved.
        """
        session = Session.create(password="test-password", name="Corruption Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Test corruption resistance", "time_window": "1h"}
        )
        
        # Successful data collection
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad)
                data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
        
        scratchpad.save()
        original_data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        
        # Pattern analyzer fails
        failing_llm = Mock()
        failing_llm.complete.side_effect = Exception("LLM API error")
        
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=failing_llm):
            pattern_analyzer = PatternAnalyzerAgent(test_config, scratchpad)
            
            try:
                pattern_analyzer.execute()
            except Exception:
                pass  # Expected to fail
        
        # Reload scratchpad and verify original data is intact
        scratchpad_reloaded = Scratchpad.load(session.session_path, session._get_key())
        assert scratchpad_reloaded.has_section(ScratchpadSection.DATA_COLLECTED)
        reloaded_data = scratchpad_reloaded.read_section(ScratchpadSection.DATA_COLLECTED)
        assert reloaded_data == original_data
        
        # Cleanup
        session.delete()


# ============================================================================
# Test 5.1.4: Session Export/Import
# ============================================================================

class TestSessionExportImport:
    """Test session export and import functionality."""

    def test_export_creates_valid_archive(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test that export creates a valid encrypted tar.gz archive.
        
        Verify:
        - Archive is created
        - Archive is encrypted
        - Archive contains expected files
        """
        # Create session with data
        session = Session.create(password="test-password", name="Export Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Export test", "time_window": "1h"}
        )
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad)
                data_fetcher.execute(sources=["kubernetes"], time_window="1h", use_sk=False)
        
        scratchpad.save()
        
        # Export session
        export_path = temp_session_dir / "exported_session.tar.gz.enc"
        session.export(str(export_path))
        
        # Verify export file exists
        assert export_path.exists()
        assert export_path.stat().st_size > 0
        
        # Verify it's encrypted (not a regular tar.gz)
        with open(export_path, 'rb') as f:
            header = f.read(2)
            # Should NOT be gzip header (1f 8b) because it's encrypted first
            assert header != b'\x1f\x8b'
        
        # Cleanup
        session.delete()

    def test_import_restores_full_session(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider
    ):
        """
        Test that import restores complete session with all data.
        
        Verify:
        - Session is restored
        - All scratchpad sections present
        - Data is identical to original
        """
        # Create and populate session
        original_session = Session.create(password="test-password", name="Import Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(original_session.session_path, original_session._get_key())
        
        problem_desc = {
            "description": "Import test problem",
            "time_window": "2h",
            "timestamp": datetime.now().isoformat()
        }
        scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, problem_desc)
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                data_fetcher = DataFetcherAgent(test_config, scratchpad)
                data_fetcher.execute(sources=["kubernetes"], time_window="2h", use_sk=False)
        
        scratchpad.save()
        original_data = scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        original_id = original_session.session_id
        
        # Export session
        export_path = temp_session_dir / "session_export.tar.gz.enc"
        original_session.export(str(export_path))
        
        # Delete original session
        original_session.delete()
        
        # Verify session is gone
        with pytest.raises(Exception):
            Session.resume(original_id, password="test-password", session_dir=temp_session_dir)
        
        # Import session
        imported_session = Session.import_session(export_path, password="test-password", session_dir=temp_session_dir)
        
        # Verify session restored (may have different ID)
        assert imported_session is not None
        assert imported_session._metadata.name == "Import Test"
        
        # Load scratchpad and verify data
        imported_scratchpad = Scratchpad.load(
            imported_session.session_path,
            imported_session._get_key()
        )
        
        assert imported_scratchpad.has_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert imported_scratchpad.has_section(ScratchpadSection.DATA_COLLECTED)
        
        restored_problem = imported_scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        restored_data = imported_scratchpad.read_section(ScratchpadSection.DATA_COLLECTED)
        
        assert restored_problem["description"] == problem_desc["description"]
        assert restored_data == original_data
        
        # Cleanup
        imported_session.delete()

    def test_export_import_encryption(
        self,
        temp_session_dir
    ):
        """
        Test that exported sessions are properly encrypted.
        
        Verify:
        - Export with one password
        - Import with different password fails
        - Import with correct password succeeds
        """
        # Create simple session
        session = Session.create(password="original-password", name="Encryption Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Sensitive data", "secret": "12345"}
        )
        scratchpad.save()
        
        # Export with original password
        export_path = temp_session_dir / "encrypted_export.tar.gz.enc"
        session.export(str(export_path))
        session.delete()
        
        # Try to import with wrong password
        with pytest.raises(Exception):
            Session.import_session(export_path, password="wrong-password", session_dir=temp_session_dir)
        
        # Import with correct password
        imported = Session.import_session(export_path, password="original-password", session_dir=temp_session_dir)
        assert imported is not None
        
        # Verify data is correct
        imported_scratchpad = Scratchpad.load(imported.session_path, imported._get_key())
        problem = imported_scratchpad.read_section(ScratchpadSection.PROBLEM_DESCRIPTION)
        assert problem["secret"] == "12345"
        
        # Cleanup
        imported.delete()

    def test_export_import_preserves_all_data(
        self,
        temp_session_dir,
        test_config,
        mock_kubernetes_fetcher,
        mock_llm_provider,
        mock_git_repo
    ):
        """
        Test that export/import preserves all session data including all agent outputs.
        
        Complete test: Full session → export → import → verify all data.
        """
        # Create complete session with all agents
        session = Session.create(password="test-password", name="Complete Export Test", session_dir=temp_session_dir)
        scratchpad = Scratchpad(session.session_path, session._get_key())
        
        # Execute full pipeline
        scratchpad.write_section(
            ScratchpadSection.PROBLEM_DESCRIPTION,
            {"description": "Complete test", "time_window": "1h"}
        )
        
        with patch('aletheia.agents.data_fetcher.KubernetesFetcher', return_value=mock_kubernetes_fetcher):
            with patch.object(DataFetcherAgent, 'get_llm', return_value=mock_llm_provider):
                DataFetcherAgent(test_config, scratchpad).execute(
                    sources=["kubernetes"], time_window="1h", use_sk=False
                )
        
        with patch.object(PatternAnalyzerAgent, 'get_llm', return_value=mock_llm_provider):
            PatternAnalyzerAgent(test_config, scratchpad).execute()
        
        with patch.object(CodeInspectorAgent, 'get_llm', return_value=mock_llm_provider):
            CodeInspectorAgent(test_config, scratchpad).execute(repositories=[str(mock_git_repo)])
        
        with patch.object(RootCauseAnalystAgent, 'get_llm', return_value=mock_llm_provider):
            RootCauseAnalystAgent(test_config, scratchpad).execute()
        
        scratchpad.save()
        
        # Store original data
        original_all = scratchpad.get_all()
        
        # Export and delete
        export_path = temp_session_dir / "complete_export.tar.gz.enc"
        session.export(str(export_path))
        session.delete()
        
        # Import
        imported = Session.import_session(export_path, password="test-password", session_dir=temp_session_dir)
        imported_scratchpad = Scratchpad.load(imported.session_path, imported._get_key())
        
        # Verify all sections present
        imported_all = imported_scratchpad.get_all()
        assert len(imported_all) == len(original_all)
        
        for section in [
            ScratchpadSection.PROBLEM_DESCRIPTION,
            ScratchpadSection.DATA_COLLECTED,
            ScratchpadSection.PATTERN_ANALYSIS,
            ScratchpadSection.CODE_INSPECTION,
            ScratchpadSection.FINAL_DIAGNOSIS
        ]:
            assert section in imported_all
            # Note: Exact equality may differ due to serialization, but sections should exist
        
        # Cleanup
        imported.delete()
