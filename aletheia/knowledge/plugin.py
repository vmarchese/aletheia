from typing import Annotated
from aletheia.knowledge import Knowledge
from aletheia.utils.logging import log_debug

class KnowledgePlugin:
    def __init__(self, knowledge_instance: Knowledge):
        self.knowledge = knowledge_instance

    def query(self, 
              question: Annotated[str, "the query to be asked to the knowledge base"]) -> str:
        """Query the knowledge base with a question and return the response."""
        log_debug(f"KnowledgePlugin: Received query: {question}")
        if question is None or question.strip() == "":
            return ""
        return self.knowledge.query(question)