from agent_framework import ChatMessageStore


class ChatMessageStoreSingleton:
    _instance: ChatMessageStore = None

    @classmethod
    def get_instance(cls) -> ChatMessageStore:
        if cls._instance is None:
            cls._instance = ChatMessageStore()
        return cls._instance