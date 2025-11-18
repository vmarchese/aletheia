"""Singleton for ChatMessageStore instance."""
from agent_framework import ChatMessageStore


class ChatMessageStoreSingleton:
    """Singleton class to manage a single ChatMessageStore instance."""
    _instance: ChatMessageStore = None

    @classmethod
    def get_instance(cls) -> ChatMessageStore:
        """Get the singleton ChatMessageStore instance."""
        if cls._instance is None:
            cls._instance = ChatMessageStore()
        return cls._instance
