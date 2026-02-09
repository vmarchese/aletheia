"""Aletheia agent response model"""

import json
from typing import Any

from pydantic import BaseModel

# Install a custom default handler so all SerializableModel instances
# work with json.dumps() directly.
_original_encoder = json.JSONEncoder.default


def _pydantic_default(self: json.JSONEncoder, obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    return _original_encoder(self, obj)


json.JSONEncoder.default = _pydantic_default  # type: ignore[assignment]


class ChartMetrics(BaseModel):
    """Represents a single metric series in a chart."""
    name: str  # Name of the metric
    values: list[float]  # Values for the metric, corresponding to the labels in ChartData
    unit: str  # Unit of the metric (e.g., "ms", "%", "requests/s")
    description: str  # Description of the metric to help users understand what it represents


class ChartData(BaseModel):
    """Represents the data for a chart."""
    labels: list[str]  # Label for the data point
    metrics: list[ChartMetrics] # Metrics for the data point


class Chart(BaseModel):
    """Represents a chart."""
    name: str  # Name of the chart
    display_hint: str  # A hint to help the user understand what the chart represents
    data: list[ChartData]  # The chart data


class ToolOutput(BaseModel):
    """Holds the output from a tool used by the agent."""
    tool_name: str  # Name of the tool
    command: str  # Command executed
    output: str  # Verbatim output from the tool


class Findings(BaseModel):
    """Holds the findings of the agent's analysis."""

    summary: str  # Summary of the findings
    details: str  # Detailed information about the findings
    tool_outputs: list[ToolOutput] = (
        []
    )  # verbatim outputs from tools used during analysis
    additional_output: str = ""  # Any additional output or observations
    skill_used: str = ""  # Skill used to derive the findings
    knowledge_searched: bool = False  # Whether external knowledge was searched
    charts: list[Chart] = []  # List of charts generated as part of the findings


class Decisions(BaseModel):
    """Holds the decisions made by the agent."""

    approach: str  # Description of the approach taken
    tools_used: list[str] = []  # List of tools used in the decision-making process
    skills_loaded: list[str] = (
        []
    )  # List of skills loaded for the decision-making process
    rationale: str  # Rationale behind the decisions made
    checklist: list[str]  # Checklist of items considered during decision-making
    additional_output: str = ""  # Any additional output or observations


class NextActions(BaseModel):
    """Holds the next actions to be taken by the agent."""

    steps: list[str]  # List of next action steps
    next_requests: list[str]  # List of next requests to be made
    additional_output: str = ""  # Any additional output or observations


class AgentResponse(BaseModel):
    """Structured response from the agent."""

    confidence: float  # Confidence level of the agent's response
    agent: str  # Name of the agent
    findings: Findings  # Holds the findings of the agent's analysis
    decisions: Decisions | None = None  # Holds the decisions made by the agent
    next_actions: NextActions | None = (
        None  # Holds the next actions to be taken by the agent
    )
    errors: list[str] = []  # Optional list of errors encountered


class TimelineEntry(BaseModel):
    """Holds a timeline entry for the troubleshooting session."""

    timestamp: str  # Timestamp of the entry
    entry_type: str  # Type of the entry (e.g., "observation", "action", "decision")
    content: str  # Content of the timeline entry


class Timeline(BaseModel):
    """Holds the timeline of the troubleshooting session."""

    entries: list[TimelineEntry]  # List of timeline entries
