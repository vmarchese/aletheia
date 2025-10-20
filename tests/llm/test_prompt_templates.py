"""Tests for prompt template management system.

This module tests the PromptTemplateLoader class and related functionality
for loading prompt templates from .md files with variable substitution,
caching, and fallback to hardcoded prompts.
"""

import tempfile
from pathlib import Path

import pytest

from aletheia.llm.prompts import (
    PromptTemplateLoader,
    configure_template_loader,
    get_template_loader,
    load_system_prompt,
    load_user_prompt,
)


class TestPromptTemplateLoader:
    """Tests for the PromptTemplateLoader class."""
    
    def test_initialization(self):
        """Test PromptTemplateLoader initialization."""
        loader = PromptTemplateLoader()
        
        # Should have templates_dir pointing to package prompts/
        assert loader.templates_dir.exists()
        assert loader.templates_dir.name == "prompts"
        
        # Should have empty cache
        assert len(loader._cache) == 0
        
        # Should have no custom_dir by default
        assert loader.custom_dir is None
    
    def test_initialization_with_custom_dir(self):
        """Test PromptTemplateLoader initialization with custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            assert loader.custom_dir == Path(tmpdir)
            assert loader.templates_dir.exists()
    
    def test_load_template_builtin(self):
        """Test loading built-in template."""
        loader = PromptTemplateLoader()
        
        # Load a built-in template
        template = loader.load_template("triage_agent_instructions")
        
        assert isinstance(template, str)
        assert len(template) > 0
        assert "triage agent" in template.lower()
        assert "specialist agents" in template.lower()
    
    def test_load_template_caching(self):
        """Test template caching."""
        loader = PromptTemplateLoader()
        
        # Load template twice
        template1 = loader.load_template("triage_agent_instructions")
        template2 = loader.load_template("triage_agent_instructions")
        
        # Should be same string (from cache)
        assert template1 == template2
        
        # Should be in cache
        assert "triage_agent_instructions" in loader._cache
    
    def test_load_template_not_found(self):
        """Test loading non-existent template raises FileNotFoundError."""
        loader = PromptTemplateLoader()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load_template("non_existent_template")
        
        assert "non_existent_template" in str(exc_info.value)
    
    def test_load_template_custom_dir_priority(self):
        """Test custom directory takes priority over built-in."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a custom template
            custom_template = Path(tmpdir) / "test_template.md"
            custom_template.write_text("This is a custom template from {source}")
            
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            # Load the custom template
            template = loader.load_template("test_template")
            
            assert template == "This is a custom template from {source}"
    
    def test_load_template_fallback_to_builtin(self):
        """Test fallback to built-in if not in custom dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            # Try to load built-in template (not in custom dir)
            template = loader.load_template("triage_agent_instructions")
            
            assert isinstance(template, str)
            assert len(template) > 0
    
    def test_load_with_variables(self):
        """Test loading template with variable substitution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template with variables
            template_path = Path(tmpdir) / "test_vars.md"
            template_path.write_text(
                "Hello {name}, your age is {age} and city is {city}."
            )
            
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            # Load with variables
            result = loader.load_with_variables(
                "test_vars",
                name="Alice",
                age=30,
                city="Boston"
            )
            
            assert result == "Hello Alice, your age is 30 and city is Boston."
    
    def test_load_with_variables_missing(self):
        """Test loading template with missing variables raises KeyError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a template with variables
            template_path = Path(tmpdir) / "test_vars.md"
            template_path.write_text("Hello {name}, your age is {age}.")
            
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            # Try to load without required variable
            with pytest.raises(KeyError) as exc_info:
                loader.load_with_variables("test_vars", name="Alice")
            
            assert "age" in str(exc_info.value)
            assert "Missing required variables" in str(exc_info.value)
    
    def test_load_with_variables_extra(self):
        """Test loading template with extra variables (should work)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / "test_vars.md"
            template_path.write_text("Hello {name}!")
            
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            # Load with extra variables (should be ignored)
            result = loader.load_with_variables(
                "test_vars",
                name="Alice",
                age=30,  # Extra variable
            )
            
            assert result == "Hello Alice!"
    
    def test_clear_cache(self):
        """Test clearing the template cache."""
        loader = PromptTemplateLoader()
        
        # Load a template
        loader.load_template("triage_agent_instructions")
        assert len(loader._cache) > 0
        
        # Clear cache
        loader.clear_cache()
        assert len(loader._cache) == 0
    
    def test_list_available_templates(self):
        """Test listing all available templates."""
        loader = PromptTemplateLoader()
        
        templates = loader.list_available_templates()
        
        # Should include built-in templates
        assert "triage_agent_instructions" in templates
        assert "data_fetcher_system" in templates
        assert "pattern_analyzer_system" in templates
        
        # Should not include README
        assert "README" not in templates
        
        # Should be sorted
        assert templates == sorted(templates)
    
    def test_list_available_templates_with_custom(self):
        """Test listing templates includes custom templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom templates
            (Path(tmpdir) / "custom1.md").write_text("Custom 1")
            (Path(tmpdir) / "custom2.md").write_text("Custom 2")
            
            loader = PromptTemplateLoader(custom_dir=tmpdir)
            
            templates = loader.list_available_templates()
            
            # Should include both built-in and custom
            assert "custom1" in templates
            assert "custom2" in templates
            assert "triage_agent_instructions" in templates


class TestGlobalTemplateLoader:
    """Tests for global template loader functions."""
    
    def test_get_template_loader_singleton(self):
        """Test get_template_loader returns singleton."""
        loader1 = get_template_loader()
        loader2 = get_template_loader()
        
        # Should be same instance
        assert loader1 is loader2
    
    def test_configure_template_loader(self):
        """Test configuring global template loader."""
        with tempfile.TemporaryDirectory() as tmpdir:
            configure_template_loader(custom_dir=tmpdir)
            
            loader = get_template_loader()
            assert loader.custom_dir == Path(tmpdir)
    
    def test_get_template_loader_with_custom_dir(self):
        """Test get_template_loader with custom directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Get loader with custom dir
            loader = get_template_loader(custom_dir=tmpdir)
            
            assert loader.custom_dir == Path(tmpdir)


class TestHelperFunctions:
    """Tests for helper functions that use PromptTemplateLoader."""
    
    def test_load_system_prompt_builtin(self):
        """Test loading system prompt from built-in templates."""
        prompt = load_system_prompt("data_fetcher")
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "data fetcher" in prompt.lower()
    
    def test_load_system_prompt_with_mode(self):
        """Test loading system prompt with mode suffix."""
        prompt = load_system_prompt("data_fetcher", mode="conversational")
        
        assert isinstance(prompt, str)
        assert "conversational" in prompt.lower() or "conversation" in prompt.lower()
    
    def test_load_system_prompt_fallback(self):
        """Test fallback to hardcoded prompts."""
        # This should fall back to hardcoded prompt
        prompt = load_system_prompt("orchestrator")
        
        assert isinstance(prompt, str)
        assert "orchestrator" in prompt.lower()
    
    def test_load_system_prompt_not_found(self):
        """Test loading non-existent system prompt raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            load_system_prompt("non_existent_agent")
        
        assert "non_existent_agent" in str(exc_info.value)
    
    def test_load_user_prompt(self):
        """Test loading user prompt with variables."""
        prompt = load_user_prompt(
            "data_fetcher_conversational",
            problem_description="Service is down",
            conversation_history="User: Check the logs",
            data_sources="Kubernetes, Prometheus"
        )
        
        assert isinstance(prompt, str)
        assert "Service is down" in prompt
        assert "Check the logs" in prompt
    
    def test_load_user_prompt_missing_variables(self):
        """Test loading user prompt with missing variables raises error."""
        with pytest.raises(KeyError):
            load_user_prompt(
                "data_fetcher_conversational",
                problem_description="Service is down"
                # Missing: conversation_history, data_sources
            )
    
    def test_load_user_prompt_fallback(self):
        """Test fallback to hardcoded user prompt templates."""
        # This should work with hardcoded template
        from aletheia.llm.prompts import get_user_prompt_template
        
        template = get_user_prompt_template("intent_understanding")
        assert template is not None


class TestIntegration:
    """Integration tests for prompt template system."""
    
    def test_end_to_end_custom_templates(self):
        """Test end-to-end flow with custom templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom templates
            (Path(tmpdir) / "my_agent_system.md").write_text(
                "You are my custom agent."
            )
            (Path(tmpdir) / "my_task.md").write_text(
                "Task: {task}\nContext: {context}"
            )
            
            # Configure global loader
            configure_template_loader(custom_dir=tmpdir)
            
            # Load system prompt
            system_prompt = load_system_prompt("my_agent")
            assert system_prompt == "You are my custom agent."
            
            # Load user prompt with variables
            user_prompt = load_user_prompt(
                "my_task",
                task="Analyze logs",
                context="Service failure"
            )
            assert user_prompt == "Task: Analyze logs\nContext: Service failure"
    
    def test_mixed_builtin_and_custom(self):
        """Test using both built-in and custom templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create custom template
            (Path(tmpdir) / "custom_agent_system.md").write_text(
                "Custom agent instructions"
            )
            
            configure_template_loader(custom_dir=tmpdir)
            
            # Load custom template
            custom = load_system_prompt("custom_agent")
            assert custom == "Custom agent instructions"
            
            # Load built-in template
            builtin = load_system_prompt("data_fetcher")
            assert "data fetcher" in builtin.lower()


class TestRealTemplates:
    """Tests using actual template files from prompts/ directory."""
    
    def test_all_templates_loadable(self):
        """Test that all template files can be loaded without errors."""
        loader = PromptTemplateLoader()
        templates = loader.list_available_templates()
        
        # Try to load each template
        for template_name in templates:
            try:
                content = loader.load_template(template_name)
                assert isinstance(content, str)
                assert len(content) > 0
            except Exception as e:
                pytest.fail(f"Failed to load template '{template_name}': {e}")
    
    def test_triage_agent_template(self):
        """Test triage agent template has expected content."""
        loader = PromptTemplateLoader()
        template = loader.load_template("triage_agent_instructions")
        
        # Check for key sections
        assert "triage agent" in template.lower()
        assert "data_fetcher" in template
        assert "pattern_analyzer" in template
        assert "code_inspector" in template
        assert "root_cause_analyst" in template
    
    def test_data_fetcher_templates(self):
        """Test data fetcher templates exist and have expected content."""
        loader = PromptTemplateLoader()
        
        # System prompt
        system = loader.load_template("data_fetcher_system")
        assert "data fetcher" in system.lower()
        assert "plugin" in system.lower()
        
        # Conversational system prompt
        conv_system = loader.load_template("data_fetcher_conversational_system")
        assert "conversational" in conv_system.lower() or "conversation" in conv_system.lower()
        
        # Conversational user prompt template (has variables)
        conv_user = loader.load_template("data_fetcher_conversational")
        assert "{problem_description}" in conv_user
        assert "{conversation_history}" in conv_user
        assert "{data_sources}" in conv_user
    
    def test_pattern_analyzer_templates(self):
        """Test pattern analyzer templates exist."""
        loader = PromptTemplateLoader()
        
        templates = loader.list_available_templates()
        assert "pattern_analyzer_system" in templates
        assert "pattern_analyzer_conversational_system" in templates
        assert "pattern_analyzer_conversational" in templates
    
    def test_code_inspector_templates(self):
        """Test code inspector templates exist."""
        loader = PromptTemplateLoader()
        
        templates = loader.list_available_templates()
        assert "code_inspector_system" in templates
        assert "code_inspector_conversational_system" in templates
        assert "code_inspector_conversational" in templates
    
    def test_root_cause_analyst_templates(self):
        """Test root cause analyst templates exist."""
        loader = PromptTemplateLoader()
        
        templates = loader.list_available_templates()
        assert "root_cause_analyst_system" in templates
        assert "root_cause_analyst_conversational_system" in templates
        assert "root_cause_analyst_conversational" in templates
    
    def test_orchestrator_templates(self):
        """Test orchestrator and routing templates exist."""
        loader = PromptTemplateLoader()
        
        templates = loader.list_available_templates()
        assert "orchestrator_system" in templates
        assert "intent_understanding_system" in templates
        assert "intent_understanding" in templates
        assert "agent_routing_system" in templates
        assert "agent_routing_decision" in templates
