"""Prompt templates and utilities for LLM agents.

This module provides prompt templates and composition utilities for all
specialist agents. Each agent has a system prompt and user prompt template
that guide the LLM's behavior.

Templates can be loaded from .md files in the prompts/ directory, allowing
easy customization and versioning without code changes.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional


class PromptTemplateLoader:
    """Loader for prompt templates from files with caching and fallback support.
    
    This class loads prompt templates from .md files in a templates directory,
    with support for custom template directories and fallback to built-in templates.
    
    Features:
    - Load templates from .md files
    - Variable substitution with {variable} syntax
    - Template caching for performance
    - Custom template directory support
    - Fallback to built-in templates
    
    Attributes:
        templates_dir: Path to the templates directory
        custom_dir: Optional path to custom templates directory
        _cache: Cache of loaded templates
    """
    
    def __init__(self, custom_dir: Optional[str] = None):
        """Initialize the prompt template loader.
        
        Args:
            custom_dir: Optional path to custom templates directory.
                       If provided and template exists there, it's used instead of built-in.
        """
        # Built-in templates directory (package-relative)
        package_dir = Path(__file__).parent.parent
        self.templates_dir = package_dir / "prompts"
        
        # Custom templates directory (user-provided)
        self.custom_dir = Path(custom_dir) if custom_dir else None
        
        # Template cache for performance
        self._cache: Dict[str, str] = {}
    
    def load_template(self, template_name: str) -> str:
        """Load a template from file.
        
        Searches for the template in this order:
        1. Custom directory (if configured)
        2. Built-in templates directory
        
        Args:
            template_name: Name of the template file (without .md extension)
        
        Returns:
            Template content as string
        
        Raises:
            FileNotFoundError: If template file is not found in any location
        """
        # Check cache first
        if template_name in self._cache:
            return self._cache[template_name]
        
        # Try custom directory first
        if self.custom_dir:
            custom_path = self.custom_dir / f"{template_name}.md"
            if custom_path.exists():
                content = custom_path.read_text(encoding="utf-8")
                self._cache[template_name] = content
                return content
        
        # Try built-in templates directory
        builtin_path = self.templates_dir / f"{template_name}.md"
        if builtin_path.exists():
            content = builtin_path.read_text(encoding="utf-8")
            self._cache[template_name] = content
            return content
        
        # Template not found
        raise FileNotFoundError(
            f"Template '{template_name}' not found in custom dir ({self.custom_dir}) "
            f"or built-in dir ({self.templates_dir})"
        )
    
    def load_with_variables(self, template_name: str, **kwargs) -> str:
        """Load a template and substitute variables.
        
        Args:
            template_name: Name of the template file (without .md extension)
            **kwargs: Variables to substitute in the template
        
        Returns:
            Template content with variables substituted
        
        Raises:
            FileNotFoundError: If template file is not found
            KeyError: If required variables are missing
        """
        template_content = self.load_template(template_name)
        
        # Extract required variables from template
        required_vars = set(re.findall(r'\{(\w+)\}', template_content))
        
        # Check for missing required variables
        provided_vars = set(kwargs.keys())
        missing = required_vars - provided_vars
        if missing:
            raise KeyError(
                f"Missing required variables for template '{template_name}': {missing}. "
                f"Required: {required_vars}, Provided: {provided_vars}"
            )
        
        # Substitute variables
        return template_content.format(**kwargs)
    
    def clear_cache(self):
        """Clear the template cache.
        
        Use this to force reload of templates after they've been modified.
        """
        self._cache.clear()
    
    def list_available_templates(self) -> list[str]:
        """List all available template names.
        
        Returns:
            List of template names (without .md extension)
        """
        templates = set()
        
        # Add built-in templates
        if self.templates_dir.exists():
            for file in self.templates_dir.glob("*.md"):
                if file.name != "README.md":
                    templates.add(file.stem)
        
        # Add custom templates
        if self.custom_dir and self.custom_dir.exists():
            for file in self.custom_dir.glob("*.md"):
                if file.name != "README.md":
                    templates.add(file.stem)
        
        return sorted(list(templates))


# Global template loader instance (can be reconfigured)
_template_loader: Optional[PromptTemplateLoader] = None


def get_template_loader(custom_dir: Optional[str] = None) -> PromptTemplateLoader:
    """Get the global template loader instance.
    
    Args:
        custom_dir: Optional custom templates directory. If provided on first call,
                   configures the global loader.
    
    Returns:
        PromptTemplateLoader instance
    """
    global _template_loader
    
    if _template_loader is None or custom_dir is not None:
        _template_loader = PromptTemplateLoader(custom_dir=custom_dir)
    
    return _template_loader


def configure_template_loader(custom_dir: Optional[str] = None):
    """Configure the global template loader with custom directory.
    
    Args:
        custom_dir: Path to custom templates directory
    """
    global _template_loader
    _template_loader = PromptTemplateLoader(custom_dir=custom_dir)


class PromptTemplate:
    """A template for generating prompts with variable substitution.
    
    Attributes:
        template: The template string with {variable} placeholders
        required_vars: Set of required variable names
    """
    
    def __init__(self, template: str):
        """Initialize a prompt template.
        
        Args:
            template: Template string with {variable} placeholders
        """
        self.template = template
        # Extract required variables from template
        import re
        self.required_vars = set(re.findall(r'\{(\w+)\}', template))
    
    def format(self, **kwargs) -> str:
        """Format the template with provided variables.
        
        Args:
            **kwargs: Variables to substitute in the template
        
        Returns:
            Formatted prompt string
        
        Raises:
            ValueError: If required variables are missing
        """
        missing = self.required_vars - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")
        
        return self.template.format(**kwargs)


# System prompts define the agent's role and behavior
# NOTE: All prompts are now loaded from .md files in the prompts/ directory
# This dictionary is kept for backwards compatibility but should use load_system_prompt()
SYSTEM_PROMPTS = {}


# User prompt templates guide specific agent tasks
# NOTE: All prompts are now loaded from .md files in the prompts/ directory
# This dictionary is kept for backwards compatibility but should use get_user_prompt_template()
USER_PROMPT_TEMPLATES = {}


def compose_messages(
    system_prompt: str,
    user_prompt: str,
    additional_context: Optional[str] = None
) -> list[Dict[str, str]]:
    """Compose a list of messages for LLM completion.
    
    Args:
        system_prompt: System prompt defining agent role
        user_prompt: User prompt with task details
        additional_context: Optional additional context to append
    
    Returns:
        List of message dictionaries ready for LLM provider
    """
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    
    if additional_context:
        user_prompt = f"{user_prompt}\n\nAdditional Context:\n{additional_context}"
    
    messages.append({"role": "user", "content": user_prompt})
    
    return messages


def get_system_prompt(agent_name: str) -> str:
    """Get the system prompt for a specific agent.
    
    This function loads system prompts from .md files in the prompts/ directory.
    
    Args:
        agent_name: Name of the agent (orchestrator, data_fetcher, etc.)
    
    Returns:
        System prompt string
    
    Raises:
        ValueError: If agent name prompt file is not found
    """
    # Use load_system_prompt which handles file loading
    return load_system_prompt(agent_name)


def get_user_prompt_template(template_name: str) -> PromptTemplate:
    """Get a user prompt template by name.
    
    This function loads the template from .md files using PromptTemplateLoader.
    
    Args:
        template_name: Name of the prompt template
    
    Returns:
        PromptTemplate instance
    
    Raises:
        ValueError: If template name is not found
    """
    # Load from file
    try:
        loader = get_template_loader()
        template_content = loader.load_template(template_name)
        return PromptTemplate(template_content)
    except FileNotFoundError as e:
        raise ValueError(
            f"Template '{template_name}' not found in prompts directory. "
            f"Expected file: {template_name}.md"
        ) from e


def load_system_prompt(agent_name: str, mode: Optional[str] = None) -> str:
    """Load a system prompt for an agent from templates directory.
    
    This function loads system prompts from .md files in the prompts/ directory.
    
    Args:
        agent_name: Name of the agent (data_fetcher, pattern_analyzer, etc.)
        mode: Optional mode suffix (e.g., "conversational" for data_fetcher_conversational_system)
    
    Returns:
        System prompt string
    
    Raises:
        ValueError: If template is not found
    """
    # Build template name
    if mode:
        template_name = f"{agent_name}_{mode}_system"
    else:
        template_name = f"{agent_name}_system"
    
    # Load from file
    try:
        loader = get_template_loader()
        return loader.load_template(template_name)
    except FileNotFoundError as e:
        raise ValueError(
            f"System prompt template '{template_name}' not found in prompts directory. "
            f"Expected file: {template_name}.md"
        ) from e


def load_user_prompt(template_name: str, **kwargs) -> str:
    """Load and format a user prompt template with variables.
    
    This function loads user prompts from .md files and substitutes variables.
    
    Args:
        template_name: Name of the template (e.g., "data_fetcher_conversational")
        **kwargs: Variables to substitute in the template
    
    Returns:
        Formatted prompt string
    
    Raises:
        ValueError: If template not found
        KeyError: If required variables are missing
    """
    # Load from file
    loader = get_template_loader()
    return loader.load_with_variables(template_name, **kwargs)
