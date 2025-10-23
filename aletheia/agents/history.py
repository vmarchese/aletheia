from typing import List, Optional
from aletheia.session import Session
from semantic_kernel.contents import ChatMessageContent

class ConversationHistory:
    """
    An agent that maintains conversation history.
    """

    def __init__(self, name: str, session: Optional[Session] = None):
        super().__init__(name, session)
        self.history: List[ChatMessageContent] = []

    def add_message(self, message: ChatMessageContent):
        self.history.append(message)

    def get_history(self) -> List[ChatMessageContent]:
        return self.history