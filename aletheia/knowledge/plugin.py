from typing import Annotated

import structlog

from aletheia.knowledge.knowledge import Knowledge

logger = structlog.get_logger(__name__)


class KnowledgePlugin:
    def __init__(self, knowledge_instance: Knowledge):
        self.knowledge = knowledge_instance

    def query(
        self, question: Annotated[str, "the query to be asked to the knowledge base"]
    ) -> str:
        """Query the knowledge base with a question and return the response."""
        logger.debug(f"KnowledgePlugin: Received query: {question}")
        if question is None or question.strip() == "":
            return ""
        return self.knowledge.query(question)
