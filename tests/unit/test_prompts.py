"""Unit tests for aletheia.llm.prompts module."""

import pytest

from aletheia.llm.prompts import (
    PromptTemplate,
    SYSTEM_PROMPTS,
    USER_PROMPT_TEMPLATES,
    compose_messages,
    get_system_prompt,
    get_user_prompt_template,
)


class TestPromptTemplate:
    """Tests for PromptTemplate class."""
    
    def test_initialization(self):
        """Test template initialization."""
        template = PromptTemplate("Hello {name}, you are {age} years old.")
        
        assert template.template == "Hello {name}, you are {age} years old."
        assert template.required_vars == {"name", "age"}
    
    def test_initialization_no_variables(self):
        """Test template with no variables."""
        template = PromptTemplate("Hello world")
        
        assert template.template == "Hello world"
        assert template.required_vars == set()
    
    def test_format_success(self):
        """Test successful template formatting."""
        template = PromptTemplate("Hello {name}, you are {age} years old.")
        
        result = template.format(name="Alice", age=30)
        
        assert result == "Hello Alice, you are 30 years old."
    
    def test_format_missing_variable(self):
        """Test formatting fails with missing variable."""
        template = PromptTemplate("Hello {name}, you are {age} years old.")
        
        with pytest.raises(ValueError, match="Missing required variables: {'age'}"):
            template.format(name="Alice")
    
    def test_format_extra_variables(self):
        """Test formatting with extra variables (should work)."""
        template = PromptTemplate("Hello {name}")
        
        result = template.format(name="Alice", age=30, city="NYC")
        
        assert result == "Hello Alice"
    
    def test_format_complex_template(self):
        """Test formatting complex multi-line template."""
        template = PromptTemplate("""Generate a {query_type} query for:

Data Source: {data_source}
Request: {request}

Return the query.""")
        
        result = template.format(
            query_type="PromQL",
            data_source="Prometheus",
            request="error rate"
        )
        
        assert "PromQL" in result
        assert "Prometheus" in result
        assert "error rate" in result


class TestSystemPrompts:
    """Tests for system prompts."""
    
    def test_all_system_prompts_exist(self):
        """Test that all expected system prompts are defined."""
        expected_agents = [
            "orchestrator",
            "data_fetcher",
            "pattern_analyzer",
            "code_inspector",
            "root_cause_analyst"
        ]
        
        for agent in expected_agents:
            assert agent in SYSTEM_PROMPTS
            assert len(SYSTEM_PROMPTS[agent]) > 0
    
    def test_orchestrator_prompt_content(self):
        """Test orchestrator prompt contains key concepts."""
        prompt = SYSTEM_PROMPTS["orchestrator"]
        
        assert "orchestrator" in prompt.lower()
        assert "coordinate" in prompt.lower() or "guide" in prompt.lower()
    
    def test_data_fetcher_prompt_content(self):
        """Test data fetcher prompt contains key concepts."""
        prompt = SYSTEM_PROMPTS["data_fetcher"]
        
        assert "data fetcher" in prompt.lower() or "fetch" in prompt.lower()
        assert "quer" in prompt.lower()  # query/queries
    
    def test_pattern_analyzer_prompt_content(self):
        """Test pattern analyzer prompt contains key concepts."""
        prompt = SYSTEM_PROMPTS["pattern_analyzer"]
        
        assert "pattern" in prompt.lower() or "analyz" in prompt.lower()
        assert "anomal" in prompt.lower()
    
    def test_code_inspector_prompt_content(self):
        """Test code inspector prompt contains key concepts."""
        prompt = SYSTEM_PROMPTS["code_inspector"]
        
        assert "code" in prompt.lower()
        assert "stack trace" in prompt.lower() or "function" in prompt.lower()
    
    def test_root_cause_analyst_prompt_content(self):
        """Test root cause analyst prompt contains key concepts."""
        prompt = SYSTEM_PROMPTS["root_cause_analyst"]
        
        assert "root cause" in prompt.lower()
        assert "synthes" in prompt.lower() or "recommend" in prompt.lower()


class TestUserPromptTemplates:
    """Tests for user prompt templates."""
    
    def test_all_templates_exist(self):
        """Test that all expected templates are defined."""
        expected_templates = [
            "data_fetcher_query_generation",
            "pattern_analyzer_log_analysis",
            "pattern_analyzer_metric_analysis",
            "code_inspector_analysis",
            "root_cause_analyst_synthesis"
        ]
        
        for template_name in expected_templates:
            assert template_name in USER_PROMPT_TEMPLATES
            assert isinstance(USER_PROMPT_TEMPLATES[template_name], PromptTemplate)
    
    def test_data_fetcher_query_generation_template(self):
        """Test data fetcher query generation template."""
        template = USER_PROMPT_TEMPLATES["data_fetcher_query_generation"]
        
        result = template.format(
            query_type="PromQL",
            data_source="Prometheus",
            request="error rate for payments-svc",
            time_window="2h",
            additional_context="Focus on 5xx errors"
        )
        
        assert "PromQL" in result
        assert "Prometheus" in result
        assert "error rate for payments-svc" in result
        assert "2h" in result
        assert "Focus on 5xx errors" in result
    
    def test_pattern_analyzer_log_analysis_template(self):
        """Test pattern analyzer log analysis template."""
        template = USER_PROMPT_TEMPLATES["pattern_analyzer_log_analysis"]
        
        result = template.format(
            log_summary="200 logs, 47 errors",
            error_clusters="NullPointerException: 45, TimeoutException: 2",
            time_range="08:05-08:07"
        )
        
        assert "200 logs, 47 errors" in result
        assert "NullPointerException" in result
        assert "08:05-08:07" in result
    
    def test_pattern_analyzer_metric_analysis_template(self):
        """Test pattern analyzer metric analysis template."""
        template = USER_PROMPT_TEMPLATES["pattern_analyzer_metric_analysis"]
        
        result = template.format(
            metrics="error_rate: 0.2 → 7.3, latency_p95: 180ms → 2.4s",
            time_range="08:00-10:00"
        )
        
        assert "error_rate" in result
        assert "latency_p95" in result
        assert "08:00-10:00" in result
    
    def test_code_inspector_analysis_template(self):
        """Test code inspector analysis template."""
        template = USER_PROMPT_TEMPLATES["code_inspector_analysis"]
        
        result = template.format(
            file_path="src/handlers/charge.go",
            function_name="processCharge",
            line_number="112",
            language="go",
            code_snippet="return *f.Enabled",
            stack_trace="charge.go:112 → features.go:57",
            git_blame="author: john.doe, commit: a3f9c2d"
        )
        
        assert "src/handlers/charge.go" in result
        assert "processCharge" in result
        assert "112" in result
        assert "return *f.Enabled" in result
        assert "john.doe" in result
    
    def test_root_cause_analyst_synthesis_template(self):
        """Test root cause analyst synthesis template."""
        template = USER_PROMPT_TEMPLATES["root_cause_analyst_synthesis"]
        
        result = template.format(
            problem_description="Payment API 500 errors",
            data_collected="200 logs with 47 errors",
            pattern_analysis="Error spike at 08:05",
            code_inspection="Nil pointer dereference at line 57"
        )
        
        assert "Payment API 500 errors" in result
        assert "200 logs with 47 errors" in result
        assert "Error spike at 08:05" in result
        assert "Nil pointer dereference" in result


class TestComposeMessages:
    """Tests for compose_messages function."""
    
    def test_compose_basic_messages(self):
        """Test composing basic system and user messages."""
        messages = compose_messages(
            system_prompt="You are an expert",
            user_prompt="Analyze this log"
        )
        
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are an expert"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Analyze this log"
    
    def test_compose_with_additional_context(self):
        """Test composing messages with additional context."""
        messages = compose_messages(
            system_prompt="You are an expert",
            user_prompt="Analyze this log",
            additional_context="Context: production system"
        )
        
        assert len(messages) == 2
        assert "Additional Context:" in messages[1]["content"]
        assert "Context: production system" in messages[1]["content"]
    
    def test_compose_without_additional_context(self):
        """Test that None additional context doesn't add anything."""
        messages = compose_messages(
            system_prompt="You are an expert",
            user_prompt="Analyze this log",
            additional_context=None
        )
        
        assert "Additional Context" not in messages[1]["content"]


class TestGetSystemPrompt:
    """Tests for get_system_prompt function."""
    
    def test_get_valid_system_prompt(self):
        """Test getting valid system prompts."""
        for agent_name in SYSTEM_PROMPTS.keys():
            prompt = get_system_prompt(agent_name)
            assert prompt == SYSTEM_PROMPTS[agent_name]
    
    def test_get_invalid_system_prompt(self):
        """Test getting invalid system prompt raises error."""
        with pytest.raises(ValueError, match="Unknown agent name: invalid_agent"):
            get_system_prompt("invalid_agent")


class TestGetUserPromptTemplate:
    """Tests for get_user_prompt_template function."""
    
    def test_get_valid_template(self):
        """Test getting valid user prompt templates."""
        for template_name in USER_PROMPT_TEMPLATES.keys():
            template = get_user_prompt_template(template_name)
            # Verify it returns a PromptTemplate with content
            assert isinstance(template, PromptTemplate)
            assert len(template.template) > 0
            assert isinstance(template.required_vars, set)
    
    def test_get_invalid_template(self):
        """Test getting invalid template raises error."""
        with pytest.raises(ValueError, match="Unknown template name: invalid_template"):
            get_user_prompt_template("invalid_template")


class TestPromptIntegration:
    """Integration tests for prompt system."""
    
    def test_full_prompt_workflow_data_fetcher(self):
        """Test full workflow for data fetcher agent."""
        # Get system prompt
        system_prompt = get_system_prompt("data_fetcher")
        
        # Get and format user prompt template
        template = get_user_prompt_template("data_fetcher_query_generation")
        user_prompt = template.format(
            query_type="PromQL",
            data_source="Prometheus",
            request="error rate",
            time_window="2h",
            additional_context="Focus on 5xx"
        )
        
        # Compose messages
        messages = compose_messages(system_prompt, user_prompt)
        
        assert len(messages) == 2
        assert "data collection" in messages[0]["content"].lower() or "data fetcher" in messages[0]["content"].lower()
        # User prompt should contain some of the request details
        assert len(messages[1]["content"]) > 0
    
    def test_full_prompt_workflow_root_cause_analyst(self):
        """Test full workflow for root cause analyst agent."""
        system_prompt = get_system_prompt("root_cause_analyst")
        
        template = get_user_prompt_template("root_cause_analyst_synthesis")
        user_prompt = template.format(
            problem_description="API errors",
            data_collected="logs and metrics",
            pattern_analysis="error spike",
            code_inspection="nil pointer"
        )
        
        messages = compose_messages(
            system_prompt,
            user_prompt,
            additional_context="Deployment at 08:04"
        )
        
        assert len(messages) == 2
        assert "root cause" in messages[0]["content"].lower()
        assert "API errors" in messages[1]["content"]
        assert "Deployment at 08:04" in messages[1]["content"]
