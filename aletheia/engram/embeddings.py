"""Embedding provider for engram using OpenAI-compatible API."""

from __future__ import annotations

from aletheia.config import sync_openai_env_vars
from aletheia.utils.logging import log_debug, log_info


class EmbeddingProvider:
    """Embedding provider using the OpenAI client.

    Works with Azure OpenAI via environment variables:
        OPENAI_BASE_URL: e.g. https://YOUR-RESOURCE.openai.azure.com/openai/v1/
        OPENAI_API_KEY: Your Azure OpenAI API key.

    Args:
        model: The deployment/model name for embeddings.
    """

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        from openai import OpenAI

        sync_openai_env_vars()
        self._model = model
        self._client = OpenAI()
        log_info(f"embedding_provider_initialized model={model}")

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float]:
        """Get embedding for a single text."""
        log_debug(f"embed_single model={self._model}")
        resp = self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return resp.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts."""
        if not texts:
            return []
        log_debug(f"embed_batch model={self._model} count={len(texts)}")
        resp = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in resp.data]

    def __getstate__(self) -> dict[str, object]:
        state = self.__dict__.copy()
        del state["_client"]
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        from openai import OpenAI

        sync_openai_env_vars()
        self.__dict__.update(state)
        self._client = OpenAI()
