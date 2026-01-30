"""Format AgentResponse objects for Telegram HTML display."""

import html as html_module

from aletheia.agents.model import AgentResponse


def format_session_header(session_id: str) -> str:
    """Create a pleasant session header for Telegram messages.

    Displays the session ID in a subtle, informative format at the top
    of messages so users always know which session they're working in.

    Args:
        session_id: The current session identifier

    Returns:
        HTML-formatted session header string
    """
    # Use a subtle format with monospace for the ID
    # The 🔗 emoji suggests connection/context without being intrusive
    return f"<code>🔗 {html_module.escape(session_id)}</code>\n{'─' * 20}\n"


def format_agent_response(
    response: AgentResponse,
    session_id: str | None = None,
    is_orchestrator: bool = False,
) -> str:
    """Convert AgentResponse to Telegram HTML format.

    Telegram HTML supports:
    - <b>bold</b>, <i>italic</i>, <u>underline</u>
    - <code>inline code</code>
    - <pre>code blocks</pre>
    - <a href="url">links</a>

    Args:
        response: Structured agent response
        session_id: Optional session ID to include as header
        is_orchestrator: If True, use simplified format for orchestrator direct responses

    Returns:
        HTML-formatted string ready for Telegram (respects 4096 char limit)
    """
    parts = []

    # Add session header if provided
    if session_id:
        parts.append(format_session_header(session_id))

    if is_orchestrator:
        # Simplified format for orchestrator direct responses - just details
        if response.findings and response.findings.details:
            details = truncate(response.findings.details, 3000)
            parts.append(html_escape(details))
    else:
        # Full structured format for agent responses
        # Agent and confidence
        parts.append(f"<b>Agent:</b> {html_escape(response.agent)}")
        if response.confidence:
            confidence_pct = int(response.confidence * 100)
            parts.append(f"<b>Confidence:</b> {confidence_pct}%")

        # Findings
        if response.findings:
            parts.append("\n<b>🔍 Findings</b>")
            if response.findings.summary:
                parts.append(html_escape(response.findings.summary))
            if response.findings.details:
                details = truncate(response.findings.details, 500)
                parts.append(html_escape(details))
            if response.findings.tool_outputs:
                parts.append("\n<b>Tool Outputs:</b>")
                # Limit to 3 tool outputs to avoid overwhelming the message
                for tool in response.findings.tool_outputs[:3]:
                    parts.append(f"<i>{html_escape(tool.tool_name)}</i>")
                    if tool.command:
                        parts.append(f"<code>{html_escape(tool.command)}</code>")
                    if tool.output:
                        output = truncate(tool.output, 300)
                        parts.append(f"<pre>{html_escape(output)}</pre>")

        # Decisions
        if response.decisions:
            parts.append("\n<b>🎯 Decisions</b>")
            if response.decisions.approach:
                parts.append(html_escape(response.decisions.approach))
            if response.decisions.tools_used:
                tools_str = ", ".join(response.decisions.tools_used[:5])
                parts.append(f"<b>Tools Used:</b> {html_escape(tools_str)}")
            if response.decisions.skills_loaded:
                skills_str = ", ".join(response.decisions.skills_loaded[:5])
                parts.append(f"<b>Skills Loaded:</b> {html_escape(skills_str)}")
            if response.decisions.checklist:
                # Limit to 5 checklist items
                for item in response.decisions.checklist[:5]:
                    parts.append(f"• {html_escape(item)}")

        # Next Actions
        if response.next_actions and response.next_actions.steps:
            parts.append("\n<b>📋 Next Actions</b>")
            # Limit to 5 steps
            for i, step in enumerate(response.next_actions.steps[:5], 1):
                parts.append(f"{i}. {html_escape(step)}")

        # Errors
        if response.errors:
            parts.append("\n<b>⚠️ Errors</b>")
            # Limit to 3 errors
            for error in response.errors[:3]:
                parts.append(f"• {html_escape(error)}")

    result = "\n".join(parts)

    # Ensure we don't exceed Telegram's limit (leave margin for splitting)
    return truncate(result, 4000)


def html_escape(text: str) -> str:
    """Escape HTML special characters for Telegram.

    Args:
        text: Text to escape

    Returns:
        HTML-escaped text safe for Telegram
    """
    return html_module.escape(text)


def truncate(text: str, max_len: int) -> str:
    """Truncate text to max length with ellipsis.

    Args:
        text: Text to truncate
        max_len: Maximum length

    Returns:
        Truncated text with "... (truncated)" suffix if needed
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n... (truncated)"


def split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split long messages into chunks respecting Telegram's 4096 char limit.

    Tries to split on newlines to maintain readability.

    Args:
        text: Text to split
        max_len: Maximum length per chunk (default: 4096 for Telegram)

    Returns:
        List of text chunks, each under max_len
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        # Find the last newline before max_len
        split_pos = remaining.rfind("\n", 0, max_len)
        if split_pos == -1:
            # No newline found, split at max_len
            split_pos = max_len

        chunks.append(remaining[:split_pos])
        remaining = remaining[split_pos:].lstrip()

    return chunks
