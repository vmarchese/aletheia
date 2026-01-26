""" Aletheia agent response model """
from typing import List
from pydantic import BaseModel


class ToolOutput(BaseModel):
    """Holds the output from a tool used by the agent."""
    tool_name: str  # Name of the tool
    command: str  # Command executed
    output: str  # Verbatim output from the tool


class Findings(BaseModel):
    """Holds the findings of the agent's analysis."""
    summary: str  # Summary of the findings
    details: str  # Detailed information about the findings
    tool_outputs: List[ToolOutput]  # verbatim outputs from tools used during analysis
    additional_output: str | None = None  # Any additional output or observations
    skill_used: str | None = None  # Skill used to derive the findings
    knowledge_searched: bool = False  # Whether external knowledge was searched


class Decisions(BaseModel):
    """Holds the decisions made by the agent."""
    approach: str  # Description of the approach taken
    tools_used: List[str]  # List of tools used in the decision-making process
    skills_loaded: List[str]  # List of skills loaded for the decision-making process
    rationale: str  # Rationale behind the decisions made
    checklist: List[str]  # Checklist of items considered during decision-making
    additional_output: str | None = None  # Any additional output or observations


class NextActions(BaseModel):
    """Holds the next actions to be taken by the agent."""
    steps: List[str]  # List of next action steps
    next_requests: List[str]  # List of next requests to be made
    additional_output: str | None = None  # Any additional output or observations


class AgentResponse(BaseModel):
    """Structured response from the agent."""
    confidence: float  # Confidence level of the agent's response
    agent: str  # Name of the agent
    findings: Findings   # Holds the findings of the agent's analysis
    decisions: Decisions  # Holds the decisions made by the agent
    next_actions: NextActions  # Holds the next actions to be taken by the agent
    errors: List[str] | None = None  # Optional list of errors encountered


class TimelineEntry(BaseModel):
    """Holds a timeline entry for the troubleshooting session."""
    timestamp: str  # Timestamp of the entry
    entry_type: str  # Type of the entry (e.g., "observation", "action", "decision")
    content: str  # Content of the timeline entry


class Timeline(BaseModel):
    """Holds the timeline of the troubleshooting session."""
    entries: List[TimelineEntry]  # List of timeline entries
