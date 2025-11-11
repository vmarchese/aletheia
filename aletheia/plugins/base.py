from typing import List
from abc import abstractmethod

from agent_framework import ToolProtocol

class BasePlugin:
    @abstractmethod
    def get_tools(): List[ToolProtocol]
