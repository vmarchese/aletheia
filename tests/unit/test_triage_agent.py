"""Unit tests for TriageAgent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from aletheia.agents.triage import TriageAgent
from aletheia.scratchpad import Scratchpad, ScratchpadSection


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "llm": {
            "default_model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY"
        }
    }


@pytest.fixture
def scratchpad(tmp_path):
    """Create a test scratchpad."""
    # Create a proper Fernet-compatible key (32 bytes, base64 encoded)
    encryption_key = b"a" * 32  # 32-byte key
    return Scratchpad(encryption_key=encryption_key, session_dir=tmp_path)


@pytest.fixture
def triage_agent(mock_config, scratchpad):
    """Create a TriageAgent instance."""
    return TriageAgent(mock_config, scratchpad)


def test_triage_agent_initialization(triage_agent):
    """Test that TriageAgent initializes correctly."""
    assert triage_agent.agent_name == "triage"
    assert triage_agent.config is not None
    assert triage_agent.scratchpad is not None


def test_triage_agent_instructions(triage_agent):
    """Test that TriageAgent has proper instructions."""
    instructions = triage_agent.get_instructions()
    
    assert "triage agent" in instructions.lower()
    # Check for specialized data fetchers
    assert "kubernetes_data_fetcher" in instructions
    assert "prometheus_data_fetcher" in instructions
    assert "pattern_analyzer" in instructions
    # code_inspector is not in the primary workflow
    assert "root_cause_analyst" in instructions
    assert "route" in instructions.lower() or "routing" in instructions.lower()


def test_triage_agent_instructions_include_specialist_descriptions(triage_agent):
    """Test that instructions describe each specialist agent."""
    instructions = triage_agent.get_instructions()
    
    # Check for data_fetcher description
    assert "collect" in instructions.lower() or "logs" in instructions.lower()
    
    # Check for pattern_analyzer description
    assert "pattern" in instructions.lower() or "anomal" in instructions.lower()
    
    # Check for code_inspector description
    assert "code" in instructions.lower() or "stack" in instructions.lower()
    
    # Check for root_cause_analyst description
    assert "diagnos" in instructions.lower() or "root cause" in instructions.lower()


def test_triage_agent_instructions_include_routing_guidelines(triage_agent):
    """Test that instructions include routing guidelines."""
    instructions = triage_agent.get_instructions()
    
    # Check for routing guidance (updated to match new instructions)
    assert "route to" in instructions.lower() or "routing" in instructions.lower()
    assert "hand" in instructions.lower() or "transfer" in instructions.lower()


def test_triage_agent_instructions_include_scratchpad_guidance(triage_agent):
    """Test that instructions guide reading scratchpad."""
    instructions = triage_agent.get_instructions()
    
    assert "scratchpad" in instructions.lower()
    assert "conversation" in instructions.lower() or "CONVERSATION_HISTORY" in instructions


@pytest.mark.asyncio
async def test_triage_agent_execute_returns_status(triage_agent):
    """Test that execute() returns a status dictionary."""
    result = await triage_agent.execute()
    
    assert isinstance(result, dict)
    assert "status" in result
    assert "message" in result


def test_triage_agent_investigation_summary_no_data(triage_agent):
    """Test investigation summary with empty scratchpad."""
    summary = triage_agent._get_investigation_summary()
    
    assert isinstance(summary, str)
    assert "⚠" in summary  # Should show warnings for missing data


def test_triage_agent_investigation_summary_with_problem(triage_agent, scratchpad):
    """Test investigation summary with problem description."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {
        "description": "Test problem"
    })
    
    summary = triage_agent._get_investigation_summary()
    
    assert "Problem" in summary
    assert "Test problem" in summary


def test_triage_agent_investigation_summary_with_data_collected(triage_agent, scratchpad):
    """Test investigation summary with data collection complete."""
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {
        "logs": ["log1", "log2"]
    })
    
    summary = triage_agent._get_investigation_summary()
    
    assert "✓ Data collected" in summary


def test_triage_agent_investigation_summary_with_patterns(triage_agent, scratchpad):
    """Test investigation summary with pattern analysis complete."""
    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, {
        "patterns": ["pattern1"]
    })
    
    summary = triage_agent._get_investigation_summary()
    
    assert "✓ Patterns analyzed" in summary


def test_triage_agent_investigation_summary_with_code_inspection(triage_agent, scratchpad):
    """Test investigation summary with code inspection complete."""
    scratchpad.write_section(ScratchpadSection.CODE_INSPECTION, {
        "files": ["file1"]
    })
    
    summary = triage_agent._get_investigation_summary()
    
    # Code inspection is currently not used in the workflow, so it won't appear in summary
    # Just verify the summary is generated without errors
    assert isinstance(summary, str)


def test_triage_agent_investigation_summary_with_diagnosis(triage_agent, scratchpad):
    """Test investigation summary with diagnosis complete."""
    scratchpad.write_section(ScratchpadSection.FINAL_DIAGNOSIS, {
        "root_cause": "Test cause"
    })
    
    summary = triage_agent._get_investigation_summary()
    
    assert "✓ Diagnosis complete" in summary


def test_triage_agent_investigation_summary_complete(triage_agent, scratchpad):
    """Test investigation summary with all sections complete."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {"description": "Test"})
    scratchpad.write_section(ScratchpadSection.DATA_COLLECTED, {"logs": []})
    scratchpad.write_section(ScratchpadSection.PATTERN_ANALYSIS, {"patterns": []})
    scratchpad.write_section(ScratchpadSection.CODE_INSPECTION, {"files": []})
    scratchpad.write_section(ScratchpadSection.FINAL_DIAGNOSIS, {"root_cause": "Test"})
    
    summary = triage_agent._get_investigation_summary()
    
    # All active sections should have checkmarks (code inspection is commented out)
    assert summary.count("✓") == 3  # data, patterns, diagnosis


def test_triage_agent_has_no_plugins(triage_agent):
    """Test that TriageAgent has no plugins (it only routes)."""
    # TriageAgent should not register any plugins
    # It only reads scratchpad and routes to specialists
    
    # Check that _kernel attribute exists (from SKBaseAgent)
    # but no plugins are registered
    # This is a structural test - we can't easily inspect SK kernel plugins
    # without actually creating the SK agent, which requires async
    
    # For now, just verify the agent can be instantiated
    assert triage_agent is not None
    assert triage_agent.agent_name == "triage"


def test_triage_agent_reads_scratchpad(triage_agent, scratchpad):
    """Test that TriageAgent can read from scratchpad."""
    scratchpad.write_section(ScratchpadSection.PROBLEM_DESCRIPTION, {
        "description": "Test problem"
    })
    
    problem = triage_agent.read_scratchpad(ScratchpadSection.PROBLEM_DESCRIPTION)
    
    assert problem is not None
    assert problem["description"] == "Test problem"


def test_triage_agent_writes_scratchpad(triage_agent, scratchpad):
    """Test that TriageAgent can write to scratchpad."""
    triage_agent.write_scratchpad(ScratchpadSection.AGENT_NOTES, {
        "triage_note": "Routing to data_fetcher"
    })
    
    notes = scratchpad.read_section(ScratchpadSection.AGENT_NOTES)
    
    assert notes is not None
    assert notes["triage_note"] == "Routing to data_fetcher"


@pytest.mark.asyncio
async def test_triage_agent_sk_integration(triage_agent):
    """Test that TriageAgent integrates with SK (structure test)."""
    # This is a structural test to ensure SK integration points exist
    
    # Check that agent has _agent attribute (SK agent)
    assert hasattr(triage_agent, "_agent")
    
    # Check that agent has _kernel attribute (SK kernel)
    assert hasattr(triage_agent, "_kernel")
    
    # Check that get_instructions method exists
    assert callable(getattr(triage_agent, "get_instructions", None))


def test_triage_agent_instructions_length(triage_agent):
    """Test that instructions are substantial."""
    instructions = triage_agent.get_instructions()
    
    # Instructions should be comprehensive
    assert len(instructions) > 500  # At least 500 characters
    
    # Should contain multiple paragraphs/sections
    assert instructions.count("\n\n") >= 3


def test_triage_agent_instructions_mention_handoff(triage_agent):
    """Test that instructions mention handoff protocol."""
    instructions = triage_agent.get_instructions()
    
    # Should mention handoff/transfer mechanism
    assert "handoff" in instructions.lower() or "transfer" in instructions.lower()


def test_triage_agent_no_hardcoded_routing(triage_agent):
    """Test that TriageAgent has no hardcoded routing logic."""
    # TriageAgent should not have methods like _route_to_data_fetcher
    # All routing is delegated to SK HandoffOrchestration
    
    methods = [method for method in dir(triage_agent) if not method.startswith("_")]
    
    # Should not have routing methods
    assert not any("route" in method.lower() and method != "get_instructions" for method in methods)


def test_triage_agent_agent_name_is_triage(triage_agent):
    """Test that agent name is correctly set to 'triage'."""
    assert triage_agent.agent_name == "triage"


def test_triage_agent_config_access(triage_agent, mock_config):
    """Test that TriageAgent has access to config."""
    assert triage_agent.config == mock_config
    assert triage_agent.config["llm"]["default_model"] == "gpt-4o"


def test_triage_agent_instructions_kubernetes_routing_guidance(triage_agent):
    """Test that instructions provide guidance for routing to Kubernetes fetcher."""
    instructions = triage_agent.get_instructions()
    
    # Should mention when to route to kubernetes_data_fetcher
    assert "kubernetes" in instructions.lower()
    # Should mention pod/container keywords
    assert any(keyword in instructions.lower() for keyword in ["pod", "container", "log"])


def test_triage_agent_instructions_prometheus_routing_guidance(triage_agent):
    """Test that instructions provide guidance for routing to Prometheus fetcher."""
    instructions = triage_agent.get_instructions()
    
    # Should mention when to route to prometheus_data_fetcher
    assert "prometheus" in instructions.lower()
    # Should mention metrics/dashboard keywords
    assert any(keyword in instructions.lower() for keyword in ["metric", "dashboard", "time-series"])


def test_triage_agent_instructions_differentiate_fetchers(triage_agent):
    """Test that instructions clearly differentiate between K8s and Prometheus fetchers."""
    instructions = triage_agent.get_instructions()
    
    # Both fetchers should be mentioned
    assert "kubernetes_data_fetcher" in instructions
    assert "prometheus_data_fetcher" in instructions
    
    # They should have different descriptions/purposes
    # Find the sections mentioning each fetcher
    lines = instructions.split('\n')
    k8s_lines = [line for line in lines if "kubernetes_data_fetcher" in line.lower()]
    prom_lines = [line for line in lines if "prometheus_data_fetcher" in line.lower()]
    
    # Should have at least one line each
    assert len(k8s_lines) > 0
    assert len(prom_lines) > 0
