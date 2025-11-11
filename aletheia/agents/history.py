from typing import List, Optional
from aletheia.session import Session

class ConversationHistory:
    """
    An agent that maintains conversation history.
    """

    def __init__(self,  session: Optional[Session] = None):

        pass
#        self.history: List[ChatMessageContent] = []
"""

    def add_message(self, message: ChatMessageContent):
        self.history.append(message)

    def get_history(self) -> List[ChatMessageContent]:
        return self.history

    def to_prompt(self) -> str:
        p = ""
        for msg in self.history:
            p += f"{msg.role}: {msg.content}\n"
        return p
        """