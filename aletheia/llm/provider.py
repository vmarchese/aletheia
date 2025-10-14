"""
LLM Provider abstraction layer.

This module provides a unified interface for interacting with various LLM providers
(OpenAI, etc.) with support for retries, rate limiting, and error handling.
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class LLMRole(str, Enum):
    """Role types for LLM messages."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    """Represents a message in an LLM conversation.
    
    Attributes:
        role: The role of the message sender (system/user/assistant)
        content: The content of the message
        name: Optional name of the message sender
        metadata: Additional metadata for the message
    """
    role: LLMRole
    content: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format."""
        msg = {
            "role": self.role.value,
            "content": self.content
        }
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass
class LLMResponse:
    """Response from an LLM provider.
    
    Attributes:
        content: The generated text content
        model: The model that generated the response
        usage: Token usage information (prompt_tokens, completion_tokens, total_tokens)
        finish_reason: Reason for completion (stop, length, etc.)
        metadata: Additional response metadata
    """
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when authentication fails."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when request times out."""
    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers.
    
    Implementations must provide:
    - complete(): Generate a completion from messages
    - supports_model(): Check if a model is supported
    """
    
    @abstractmethod
    def complete(
        self,
        messages: Union[str, List[LLMMessage]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a completion from the given messages.
        
        Args:
            messages: Either a string (converted to user message) or list of LLMMessage objects
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse containing the generated text and metadata
            
        Raises:
            LLMError: Base exception for LLM errors
            LLMRateLimitError: When rate limit is exceeded
            LLMAuthenticationError: When authentication fails
            LLMTimeoutError: When request times out
        """
        pass
    
    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """Check if the provider supports a given model.
        
        Args:
            model: Model name to check
            
        Returns:
            True if the model is supported, False otherwise
        """
        pass
    
    def _normalize_messages(self, messages: Union[str, List[LLMMessage]]) -> List[LLMMessage]:
        """Normalize input messages to list of LLMMessage objects.
        
        Args:
            messages: Either a string or list of LLMMessage objects
            
        Returns:
            List of LLMMessage objects
        """
        if isinstance(messages, str):
            return [LLMMessage(role=LLMRole.USER, content=messages)]
        return messages


class OpenAIProvider(LLMProvider):
    """OpenAI API provider implementation.
    
    Supports models: gpt-4o, gpt-4o-mini, o1-preview, o1-mini
    
    Attributes:
        api_key: OpenAI API key
        model: Default model to use
        base_url: Optional custom base URL
    """
    
    # Supported OpenAI models
    SUPPORTED_MODELS = {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4o-2024-08-06",
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1-preview",
        "o1-mini",
    }
    
    # Default timeout in seconds
    DEFAULT_TIMEOUT = 60
    
    # Max retries for rate limit errors
    MAX_RETRIES = 3
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        base_url: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Default model to use
            base_url: Optional custom base URL
            timeout: Default timeout in seconds
            
        Raises:
            LLMAuthenticationError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise LLMAuthenticationError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model
        self.base_url = base_url
        self.default_timeout = timeout
        
        # Lazy import of openai
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package not installed. Install with: pip install openai"
                )
            
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            
            self._client = OpenAI(**kwargs)
        
        return self._client
    
    def complete(
        self,
        messages: Union[str, List[LLMMessage]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a completion using OpenAI API.
        
        Args:
            messages: Either a string or list of LLMMessage objects
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional OpenAI parameters (top_p, frequency_penalty, etc.)
            
        Returns:
            LLMResponse with generated content and metadata
            
        Raises:
            LLMRateLimitError: When rate limit is exceeded
            LLMAuthenticationError: When API key is invalid
            LLMTimeoutError: When request times out
            LLMError: For other API errors
        """
        normalized_messages = self._normalize_messages(messages)
        
        # Convert to OpenAI format
        api_messages = [msg.to_dict() for msg in normalized_messages]
        
        # Build request parameters
        request_params = {
            "model": kwargs.pop("model", self.model),
            "messages": api_messages,
            "temperature": temperature,
            "timeout": timeout or self.default_timeout,
        }
        
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
        
        # Add any additional kwargs
        request_params.update(kwargs)
        
        # Retry logic for rate limits
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(**request_params)
                
                # Extract response data
                choice = response.choices[0]
                
                return LLMResponse(
                    content=choice.message.content or "",
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                    finish_reason=choice.finish_reason,
                    metadata={
                        "id": response.id,
                        "created": response.created,
                    }
                )
            
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Check for specific error types
                if "rate_limit" in error_msg or "rate limit" in error_msg:
                    if attempt < self.MAX_RETRIES - 1:
                        # Exponential backoff: 1s, 2s, 4s
                        wait_time = 2 ** attempt
                        time.sleep(wait_time)
                        continue
                    raise LLMRateLimitError(f"Rate limit exceeded after {self.MAX_RETRIES} retries: {e}")
                
                elif "authentication" in error_msg or "api_key" in error_msg or "unauthorized" in error_msg:
                    raise LLMAuthenticationError(f"Authentication failed: {e}")
                
                elif "timeout" in error_msg:
                    raise LLMTimeoutError(f"Request timed out: {e}")
                
                else:
                    raise LLMError(f"OpenAI API error: {e}")
        
        # If we exhausted retries
        raise LLMError(f"Failed after {self.MAX_RETRIES} retries: {last_error}")
    
    def supports_model(self, model: str) -> bool:
        """Check if the model is supported by OpenAI.
        
        Args:
            model: Model name to check
            
        Returns:
            True if supported, False otherwise
        """
        # Check exact match
        if model in self.SUPPORTED_MODELS:
            return True
        
        # Check prefixes for versioned models
        for supported in self.SUPPORTED_MODELS:
            if model.startswith(supported):
                return True
        
        return False


class LLMFactory:
    """Factory for creating LLM provider instances.
    
    Supports caching of provider instances for performance.
    """
    
    _cache: Dict[str, LLMProvider] = {}
    
    @classmethod
    def create_provider(
        cls,
        config: Dict[str, Any],
        use_cache: bool = True
    ) -> LLMProvider:
        """Create an LLM provider from configuration.
        
        Args:
            config: Configuration dictionary with keys:
                - model: Model name (required)
                - api_key: API key (optional, can use env var)
                - api_key_env: Environment variable name for API key (optional)
                - base_url: Custom base URL (optional)
                - timeout: Request timeout in seconds (optional)
            use_cache: Whether to use cached provider instances
            
        Returns:
            Configured LLMProvider instance
            
        Raises:
            ValueError: If model is not supported by any provider
            
        Example:
            >>> config = {"model": "gpt-4o", "timeout": 30}
            >>> provider = LLMFactory.create_provider(config)
            >>> response = provider.complete("Hello, world!")
        """
        model = config.get("model", "gpt-4o")
        
        # Create cache key
        cache_key = f"{model}:{config.get('api_key_env', 'OPENAI_API_KEY')}"
        
        # Check cache
        if use_cache and cache_key in cls._cache:
            return cls._cache[cache_key]
        
        # Determine provider based on model
        if model.startswith("gpt-") or model.startswith("o1"):
            # Get API key from config or environment
            api_key = config.get("api_key")
            if not api_key and "api_key_env" in config:
                api_key = os.getenv(config["api_key_env"])
            
            provider = OpenAIProvider(
                api_key=api_key,
                model=model,
                base_url=config.get("base_url"),
                timeout=config.get("timeout", OpenAIProvider.DEFAULT_TIMEOUT)
            )
            
            # Cache the provider
            if use_cache:
                cls._cache[cache_key] = provider
            
            return provider
        
        else:
            raise ValueError(
                f"Unsupported model: {model}. "
                f"Supported models: {', '.join(OpenAIProvider.SUPPORTED_MODELS)}"
            )
    
    @classmethod
    def clear_cache(cls):
        """Clear the provider cache."""
        cls._cache.clear()
