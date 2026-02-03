"""Shared formatting utilities for rendering agent responses across channels."""


def format_response_to_markdown(response_data: dict) -> str:
    """Format agent response JSON to markdown.

    Args:
        response_data: Parsed AgentResponse JSON

    Returns:
        Markdown-formatted string
    """
    parts = []

    agent_name = response_data.get("agent", "Orchestrator")
    agent_lower = agent_name.lower() if agent_name else ""
    is_orchestrator = agent_lower in ("orchestrator", "aletheia")

    if is_orchestrator:
        # Simplified rendering for orchestrator
        if "findings" in response_data:
            findings = response_data["findings"]
            if isinstance(findings, dict):
                if "summary" in findings and findings["summary"]:
                    parts.append(findings["summary"])
                if "details" in findings and findings["details"]:
                    parts.append(f"\n\n{findings['details']}")
        if "errors" in response_data and response_data["errors"]:
            parts.append("\n\n⚠️ **Errors:**")
            for error in response_data["errors"]:
                parts.append(f"\n- {error}")
    else:
        # Full structured rendering for agent responses
        if "confidence" in response_data:
            confidence_pct = int(response_data["confidence"] * 100)
            parts.append(f"**Agent:** {agent_name} | **Confidence:** {confidence_pct}%")
        else:
            parts.append(f"**Agent:** {agent_name}")

        if "findings" in response_data:
            findings = response_data["findings"]
            if isinstance(findings, dict):
                parts.append("\n\n## 🔍 Findings\n")
                if "summary" in findings and findings["summary"]:
                    parts.append(f"**Summary:**\n\n{findings['summary']}\n")
                if "details" in findings and findings["details"]:
                    parts.append(f"\n**Details:**\n\n{findings['details']}\n")

        if "decisions" in response_data:
            decisions = response_data["decisions"]
            if isinstance(decisions, dict):
                parts.append("\n## 🎯 Decisions\n")
                if "approach" in decisions and decisions["approach"]:
                    parts.append(f"**Approach:**\n\n{decisions['approach']}\n")

        if "next_actions" in response_data:
            next_actions = response_data["next_actions"]
            if isinstance(next_actions, dict):
                parts.append("\n## 📋 Next Actions\n")
                if "steps" in next_actions and next_actions["steps"]:
                    for i, step in enumerate(next_actions["steps"], 1):
                        parts.append(f"\n{i}. {step}")

        if "errors" in response_data and response_data["errors"]:
            parts.append("\n\n## ⚠️ Errors\n")
            for error in response_data["errors"]:
                parts.append(f"\n- {error}")

    return "".join(parts)
