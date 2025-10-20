"""Unit tests for Pattern Analyzer Agent (SK-based)."""

import pytest
from unittest.mock import Mock, patch

from aletheia.agents.pattern_analyzer import PatternAnalyzerAgent
from aletheia.scratchpad import Scratchpad, ScratchpadSection


class TestPatternAnalyzerInitialization:
    """Test Pattern Analyzer Agent initialization."""
    
    def test_initialization(self):
        """Test basic initialization."""
        config = {"llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}}
        scratchpad = Mock(spec=Scratchpad)
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        assert agent.agent_name == "pattern_analyzer"
        assert agent.config == config
        assert agent.scratchpad == scratchpad


class TestExecuteIntegration:
    """Test full agent execution."""
    
    def test_execute_no_data_error(self):
        """Test execution fails when no data collected."""
        config = {"llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}}
        scratchpad = Mock(spec=Scratchpad)
        scratchpad.read_section.return_value = None
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        
        with pytest.raises(ValueError, match="No data collected"):
            agent.execute()
    
    @patch('aletheia.agents.pattern_analyzer.PatternAnalyzerAgent.invoke')
    def test_execute_success(self, mock_invoke):
        """Test successful execution with mocked LLM."""
        config = {"llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}}
        scratchpad = Mock(spec=Scratchpad)
        
        # Mock scratchpad data
        scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.DATA_COLLECTED: {
                "kubernetes": {"count": 100, "summary": "100 logs"}
            },
            ScratchpadSection.PROBLEM_DESCRIPTION: {
                "description": "API errors"
            },
            ScratchpadSection.CONVERSATION_HISTORY: None
        }.get(section)
        
        # Mock LLM response
        mock_invoke.return_value = """{
            "summary": "Analysis complete",
            "key_findings": ["High error rate"],
            "anomalies": [],
            "confidence": 0.8
        }"""
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        result = agent.execute()
        
        assert result["success"] is True
        assert result["analysis_complete"] is True
        assert "summary" in result
        
        # Verify scratchpad was written
        scratchpad.write_section.assert_called_once()


class TestConversationalMode:
    """Test conversational mode functionality."""
    
    @patch('aletheia.agents.pattern_analyzer.PatternAnalyzerAgent.invoke')
    def test_execute_conversational_mode(self, mock_invoke):
        """Test execution in conversational mode."""
        config = {"llm": {"default_model": "gpt-4o", "api_key_env": "OPENAI_API_KEY"}}
        scratchpad = Mock(spec=Scratchpad)
        
        # Mock with conversation history
        scratchpad.read_section.side_effect = lambda section: {
            ScratchpadSection.DATA_COLLECTED: {"kubernetes": {"count": 100}},
            ScratchpadSection.PROBLEM_DESCRIPTION: {"description": "Errors"},
            ScratchpadSection.CONVERSATION_HISTORY: [
                {"role": "user", "content": "Check the logs"}
            ]
        }.get(section)
        
        mock_invoke.return_value = '{"summary": "Found issues", "anomalies": [], "confidence": 0.9}'
        
        agent = PatternAnalyzerAgent(config, scratchpad)
        result = agent.execute()
        
        assert result["success"] is True
        assert result["conversational_mode"] is True
