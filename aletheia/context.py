"""Context window management for Aletheia sessions.

Provides active context management by tracking, measuring, and trimming
the different sections of the LLM context window (system prompt, tools,
messages, memory files). Integrates with the agent_framework's context
provider pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimate token count using chars/4 heuristic.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count (minimum 0).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def _format_tokens(count: int) -> str:
    """Format token count with k suffix for readability."""
    if count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


@dataclass
class ContextSection:
    """A labeled section of the context window."""

    name: str
    token_count: int
    color: str
    details: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class ContextWindow:
    """Snapshot of the current context window allocation.

    Built from measurements stored by ContextWindowProvider during
    each agent.run() call. Provides rendering for the /context command.
    """

    model: str
    provider: str
    max_tokens: int
    sections: list[ContextSection]
    total_input_tokens: int = 0
    reserved_ratio: float = 0.225

    @property
    def reserved_tokens(self) -> int:
        """Tokens reserved as buffer."""
        return int(self.max_tokens * self.reserved_ratio)

    @property
    def estimated_used(self) -> int:
        """Sum of all section token estimates."""
        return sum(s.token_count for s in self.sections)

    @property
    def free_tokens(self) -> int:
        """Remaining available tokens."""
        return max(0, self.max_tokens - self.estimated_used - self.reserved_tokens)

    @property
    def utilization_pct(self) -> float:
        """Context utilization as a percentage."""
        if self.max_tokens <= 0:
            return 0.0
        return self.estimated_used / self.max_tokens * 100

    @classmethod
    def from_state(
        cls,
        state: dict[str, Any],
        config: Any,
        total_input_tokens: int = 0,
        model: str = "unknown",
        provider: str = "unknown",
    ) -> ContextWindow:
        """Rebuild a ContextWindow from stored provider state.

        Args:
            state: The provider state dict from session.state["context_window"].
            config: Aletheia Config object.
            total_input_tokens: Actual token count from API response.
            model: LLM model name.
            provider: LLM provider name.

        Returns:
            A ContextWindow snapshot.
        """
        max_tokens = config.max_context_window if config else 1_000_000
        reserved_ratio = (
            config.context_reserved_ratio
            if config and hasattr(config, "context_reserved_ratio")
            else 0.225
        )

        # Rebuild sections from stored measurements
        section_defs = [
            ("System prompt", "system_prompt_tokens", "\U0001f7e6"),  # blue
            ("Tools", "tools_tokens", "\U0001f7e9"),  # green
            ("Memory files", "memory_tokens", "\U0001f7e8"),  # yellow
            ("Messages", "messages_tokens", "\U0001f7ea"),  # purple
        ]

        sections: list[ContextSection] = []
        for name, key, color in section_defs:
            token_count = state.get(key, 0)
            details_key = f"{key}_details"
            details = state.get(details_key, [])
            sections.append(
                ContextSection(
                    name=name,
                    token_count=token_count,
                    color=color,
                    details=details,
                )
            )

        actual_total = state.get("actual_input_tokens", total_input_tokens)

        return cls(
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            sections=sections,
            total_input_tokens=actual_total,
            reserved_ratio=reserved_ratio,
        )

    def render(self) -> str:
        """Render the context window as a formatted string for display.

        Returns:
            Formatted string with visual bar and section breakdown.
        """
        bar_length = 20
        used_pct = self.utilization_pct
        reserved_pct = self.reserved_ratio * 100
        free_pct = max(0, 100 - used_pct - reserved_pct)

        # Build proportional bar
        bar_chars: list[str] = []
        remaining_blocks = bar_length

        for section in self.sections:
            if self.max_tokens > 0:
                blocks = round(section.token_count / self.max_tokens * bar_length)
            else:
                blocks = 0
            blocks = min(blocks, remaining_blocks)
            bar_chars.extend([section.color] * blocks)
            remaining_blocks -= blocks

        # Free space blocks (white)
        free_blocks = round(free_pct / 100 * bar_length)
        free_blocks = min(free_blocks, remaining_blocks)
        bar_chars.extend(["\u2b1c"] * free_blocks)  # white square
        remaining_blocks -= free_blocks

        # Reserved buffer blocks (black)
        bar_chars.extend(["\u2b1b"] * remaining_blocks)  # black square

        bar_str = " ".join(bar_chars)

        # Use actual tokens if available, otherwise estimated
        display_used = (
            self.total_input_tokens
            if self.total_input_tokens > 0
            else self.estimated_used
        )

        lines: list[str] = []
        lines.append("## Context Usage\n")
        lines.append(f"{bar_str}\n")
        lines.append(
            f"{self.model} \u00b7 "
            f"{_format_tokens(display_used)}/{_format_tokens(self.max_tokens)} "
            f"tokens ({self.utilization_pct:.1f}%)\n"
        )

        # Section breakdown
        for section in self.sections:
            pct = (
                section.token_count / self.max_tokens * 100
                if self.max_tokens > 0
                else 0
            )
            lines.append(
                f"  {section.color} {section.name}: "
                f"{_format_tokens(section.token_count)} tokens ({pct:.1f}%)"
            )

        # Free space
        lines.append(
            f"  \u2b1c Free space: "
            f"{_format_tokens(self.free_tokens)} ({free_pct:.1f}%)"
        )

        # Reserved buffer
        lines.append(
            f"  \u2b1b Reserved buffer: "
            f"{_format_tokens(self.reserved_tokens)} tokens ({reserved_pct:.1f}%)"
        )

        # Memory files detail
        memory_section = next(
            (s for s in self.sections if s.name == "Memory files"), None
        )
        if memory_section and memory_section.details:
            lines.append("")
            lines.append("### Memory files\n")
            for file_path, tokens in memory_section.details:
                lines.append(f"  {file_path}: {tokens} tokens")

        # Warning
        if self.utilization_pct > 80:
            lines.append("")
            lines.append(
                "**Warning:** Context window is over 80% full. "
                "Consider starting a new session."
            )

        return "\n".join(lines)

    def render_dump(
        self,
        instructions: str = "",
        tools: list[Any] | None = None,
        messages: list[Any] | None = None,
        memory_contents: list[tuple[str, str]] | None = None,
    ) -> str:
        """Render a full dump of the context window contents.

        Args:
            instructions: The system prompt / instructions text.
            tools: List of tool objects (with .name, .description).
            messages: List of conversation messages.
            memory_contents: List of (file_path, content) pairs.

        Returns:
            Formatted markdown string with all context sections.
        """
        display_used = (
            self.total_input_tokens
            if self.total_input_tokens > 0
            else self.estimated_used
        )

        lines: list[str] = []
        lines.append("## Context Dump\n")
        lines.append(
            f"{self.model} \u00b7 {self.provider} \u00b7 "
            f"{_format_tokens(display_used)}/{_format_tokens(self.max_tokens)} "
            f"tokens ({self.utilization_pct:.1f}%)\n"
        )

        # --- System Prompt ---
        sys_section = next(
            (s for s in self.sections if s.name == "System prompt"), None
        )
        sys_tokens = _format_tokens(sys_section.token_count) if sys_section else "0"
        lines.append("---\n")
        lines.append(f"### System Prompt ({sys_tokens} tokens)\n")
        if instructions:
            lines.append("```")
            lines.append(instructions)
            lines.append("```\n")
        else:
            lines.append("*No instructions available.*\n")

        # --- Tools ---
        tools_section = next((s for s in self.sections if s.name == "Tools"), None)
        tools_tokens = (
            _format_tokens(tools_section.token_count) if tools_section else "0"
        )
        lines.append("---\n")
        lines.append(f"### Tools ({tools_tokens} tokens)\n")
        if tools:
            lines.append("| Tool | Description |")
            lines.append("|------|-------------|")
            for t in tools:
                name = getattr(t, "name", str(t))
                desc = getattr(t, "description", "") or ""
                # Truncate long descriptions for readability
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                lines.append(f"| {name} | {desc} |")
            lines.append("")
        else:
            lines.append("*No tools registered.*\n")

        # --- Memory Files ---
        mem_section = next((s for s in self.sections if s.name == "Memory files"), None)
        mem_tokens = _format_tokens(mem_section.token_count) if mem_section else "0"
        lines.append("---\n")
        lines.append(f"### Memory Files ({mem_tokens} tokens)\n")
        if memory_contents:
            for file_path, content in memory_contents:
                file_tokens = estimate_tokens(content) if content else 0
                lines.append(f"**{file_path}** ({_format_tokens(file_tokens)} tokens)")
                lines.append("```")
                lines.append(content if content else "(empty)")
                lines.append("```\n")
        else:
            lines.append("*No memory files found.*\n")

        # --- Messages ---
        msg_section = next((s for s in self.sections if s.name == "Messages"), None)
        msg_tokens = _format_tokens(msg_section.token_count) if msg_section else "0"
        lines.append("---\n")
        msg_count = len(messages) if messages else 0
        lines.append(f"### Messages ({msg_tokens} tokens, {msg_count} messages)\n")
        if messages:
            # Show most recent messages, cap at 20 to avoid enormous output
            max_show = 20
            if len(messages) > max_show:
                lines.append(
                    f"*Showing most recent {max_show} "
                    f"of {len(messages)} messages.*\n"
                )
            for msg in messages[-max_show:]:
                role = getattr(msg, "role", None) or "unknown"
                text = _format_message_text(msg)
                # Truncate very long messages
                if len(text) > 500:
                    text = text[:497] + "..."
                lines.append(f"**{role}**: {text}\n")
        else:
            lines.append("*No messages in history.*\n")

        # --- Summary Table ---
        lines.append("---\n")
        lines.append("### Summary\n")
        lines.append("| Section | Tokens | % |")
        lines.append("|---------|--------|---|")
        for section in self.sections:
            pct = (
                section.token_count / self.max_tokens * 100
                if self.max_tokens > 0
                else 0
            )
            lines.append(
                f"| {section.name} | "
                f"{_format_tokens(section.token_count)} | {pct:.1f}% |"
            )
        lines.append(
            f"| **Total Used** | "
            f"**{_format_tokens(self.estimated_used)}** | "
            f"**{self.utilization_pct:.1f}%** |"
        )
        lines.append(
            f"| Free | "
            f"{_format_tokens(self.free_tokens)} | "
            f"{max(0, 100 - self.utilization_pct - self.reserved_ratio * 100):.1f}% |"
        )
        lines.append(
            f"| Reserved | "
            f"{_format_tokens(self.reserved_tokens)} | "
            f"{self.reserved_ratio * 100:.1f}% |"
        )

        return "\n".join(lines)

    def render_dump_data(
        self,
        instructions: str = "",
        tools: list[Any] | None = None,
        messages: list[Any] | None = None,
        memory_contents: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Render context dump as structured data for the web channel.

        Returns a JSON-serializable dict with all context sections and
        token metrics for rich frontend rendering.
        """
        display_used = (
            self.total_input_tokens
            if self.total_input_tokens > 0
            else self.estimated_used
        )
        used_for_pct = max(self.estimated_used, 1)
        max_for_pct = max(self.max_tokens, 1)

        # Map section names to keys and content
        section_key_map: dict[str, str] = {
            "System prompt": "system_prompt",
            "Tools": "tools",
            "Memory files": "memory_files",
            "Messages": "messages",
        }

        # Build tools content
        tools_content: list[dict[str, str]] = []
        for t in tools or []:
            name = getattr(t, "name", str(t))
            desc = getattr(t, "description", "") or ""
            if len(desc) > 80:
                desc = desc[:77] + "..."
            tools_content.append({"name": name, "description": desc})

        # Build memory content
        memory_content: list[dict[str, Any]] = []
        for file_path, content in memory_contents or []:
            memory_content.append(
                {
                    "path": file_path,
                    "content": content if content else "(empty)",
                    "tokens": estimate_tokens(content) if content else 0,
                }
            )

        # Build messages content (cap at 20)
        max_show = 20
        msgs = messages or []
        messages_content: list[dict[str, str]] = []
        for msg in msgs[-max_show:]:
            role = getattr(msg, "role", None) or "unknown"
            text = _format_message_text(msg)
            if len(text) > 500:
                text = text[:497] + "..."
            messages_content.append({"role": role, "text": text})

        # Map section keys to their content
        content_map: dict[str, Any] = {
            "system_prompt": instructions or "",
            "tools": tools_content,
            "memory_files": memory_content,
            "messages": messages_content,
        }

        sections_data: list[dict[str, Any]] = []
        for section in self.sections:
            key = section_key_map.get(section.name, section.name.lower())
            entry: dict[str, Any] = {
                "name": section.name,
                "key": key,
                "color": section.color,
                "token_count": section.token_count,
                "pct_of_used": round(section.token_count / used_for_pct * 100, 1),
                "pct_of_max": round(section.token_count / max_for_pct * 100, 1),
                "content": content_map.get(key, ""),
            }
            if key == "messages":
                entry["total_count"] = len(msgs)
            sections_data.append(entry)

        free_pct = round(
            max(0, 100 - self.utilization_pct - self.reserved_ratio * 100),
            1,
        )

        return {
            "model": self.model,
            "provider": self.provider,
            "max_tokens": self.max_tokens,
            "estimated_used": self.estimated_used,
            "display_used": display_used,
            "utilization_pct": round(self.utilization_pct, 1),
            "free_tokens": self.free_tokens,
            "free_pct": free_pct,
            "reserved_tokens": self.reserved_tokens,
            "reserved_pct": round(self.reserved_ratio * 100, 1),
            "sections": sections_data,
        }


def _measure_tools(tools: list[Any]) -> int:
    """Estimate tokens for tool definitions.

    Args:
        tools: List of FunctionTool objects.

    Returns:
        Estimated total token count for all tool schemas.
    """
    total = 0
    for tool in tools:
        parts: list[str] = []
        if hasattr(tool, "name"):
            parts.append(str(tool.name))
        if hasattr(tool, "description") and tool.description:
            parts.append(str(tool.description))
        if hasattr(tool, "parameters") and callable(tool.parameters):
            try:
                params = tool.parameters()
                parts.append(json.dumps(params))
            except Exception:
                pass
        total += estimate_tokens(" ".join(parts))
    return total


def _serialize_message(msg: Any) -> str:
    """Serialize a message to a string suitable for token estimation.

    Uses to_json() for agent_framework Message objects (which lack __str__),
    falls back to str() for plain objects.
    """
    if hasattr(msg, "to_json"):
        try:
            return msg.to_json()
        except Exception:
            pass
    return str(msg)


def _format_message_text(msg: Any) -> str:
    """Extract a human-readable summary from a message.

    For agent_framework Message objects, extracts text content and
    summarizes tool calls/results. Falls back to str() for other types.
    """
    # Try .text property first (agent_framework Message)
    text = getattr(msg, "text", None) or ""
    if text:
        return text

    # No text — look at individual contents for tool calls/results
    contents = getattr(msg, "contents", None)
    if contents:
        parts: list[str] = []
        for content in contents:
            ctype = getattr(content, "type", "")
            if ctype == "function_call":
                name = getattr(content, "name", "unknown")
                parts.append(f"[call: {name}]")
            elif ctype == "function_result":
                name = getattr(content, "name", "unknown")
                result = str(getattr(content, "result", "") or "")
                if len(result) > 200:
                    result = result[:197] + "..."
                parts.append(f"[result: {name}] {result}")
            elif ctype == "text" and getattr(content, "text", None):
                parts.append(content.text)
            else:
                parts.append(f"[{ctype}]")
        if parts:
            return " ".join(parts)

    return "(empty)"


def _measure_messages(messages: list[Any]) -> int:
    """Estimate tokens for a list of messages.

    Args:
        messages: List of Message objects.

    Returns:
        Estimated total token count.
    """
    total = 0
    for msg in messages:
        total += estimate_tokens(_serialize_message(msg))
    return total


def _measure_memory_files() -> tuple[int, list[tuple[str, int]]]:
    """Measure engram memory files on disk.

    Returns:
        Tuple of (total_tokens, details) where details is a list of
        (file_path, token_count) pairs.
    """
    try:
        from aletheia.config import get_config_dir

        config_dir = get_config_dir()
        details: list[tuple[str, int]] = []
        total = 0

        # Long-term memory
        memory_file = config_dir / "MEMORY.md"
        if memory_file.exists():
            content = memory_file.read_text(encoding="utf-8")
            tokens = estimate_tokens(content)
            details.append((str(memory_file), tokens))
            total += tokens

        # Daily memories (recent 3 days)
        memory_dir = config_dir / "memory"
        if memory_dir.exists():
            for daily_file in sorted(memory_dir.glob("*.md"), reverse=True)[:3]:
                content = daily_file.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
                details.append((str(daily_file), tokens))
                total += tokens

        return total, details
    except Exception as e:
        logger.debug(f"Could not measure memory files: {e}")
        return 0, []


class ContextWindowProvider:
    """Context provider that tracks section sizes and manages context budget.

    Implements the agent_framework BaseContextProvider interface via duck
    typing (source_id, before_run, after_run). Runs after
    InMemoryHistoryProvider to see the full assembled context. Measures
    each section, stores measurements in session state, and trims history
    messages when the context exceeds the budget.
    """

    def __init__(self, max_tokens: int, reserved_ratio: float = 0.225) -> None:
        """Initialize the context window provider.

        Args:
            max_tokens: Maximum context window size in tokens.
            reserved_ratio: Fraction of context reserved as buffer (0.0-0.5).
        """
        self.source_id = "context_window"
        self.max_tokens = max_tokens
        self.reserved_ratio = reserved_ratio

    @property
    def _budget(self) -> int:
        """Available token budget (max minus reserved)."""
        return self.max_tokens - int(self.max_tokens * self.reserved_ratio)

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
    ) -> None:
        """Measure context sections and trim history if over budget.

        Runs after InMemoryHistoryProvider has loaded history into
        context.context_messages.
        """
        # 1. Measure system prompt
        instructions = getattr(agent, "default_options", {}).get("instructions", "")
        system_prompt_tokens = estimate_tokens(instructions) if instructions else 0

        # 2. Measure tools
        tools = getattr(agent, "default_options", {}).get("tools", [])
        tools_tokens = _measure_tools(tools) if tools else 0

        # 3. Measure memory files
        memory_tokens, memory_details = _measure_memory_files()

        # 4. Measure history messages (loaded by InMemoryHistoryProvider)
        history_messages = context.context_messages.get("in_memory", [])
        messages_tokens = _measure_messages(history_messages)

        # 5. Measure input messages
        input_tokens = _measure_messages(context.input_messages)
        messages_tokens += input_tokens

        # 6. Store measurements
        state["system_prompt_tokens"] = system_prompt_tokens
        state["tools_tokens"] = tools_tokens
        state["memory_tokens"] = memory_tokens
        state["memory_tokens_details"] = memory_details
        state["messages_tokens"] = messages_tokens
        state["message_count"] = len(history_messages) + len(context.input_messages)

        total_estimated = (
            system_prompt_tokens + tools_tokens + memory_tokens + messages_tokens
        )
        state["total_estimated"] = total_estimated

        # 7. Trim history if over budget
        fixed_cost = system_prompt_tokens + tools_tokens + memory_tokens + input_tokens
        history_budget = self._budget - fixed_cost

        if history_budget < 0:
            history_budget = 0

        if history_messages and _measure_messages(history_messages) > history_budget:
            trimmed = self._trim_messages(history_messages, history_budget, session)
            context.context_messages["in_memory"] = trimmed
            state["messages_tokens"] = _measure_messages(trimmed) + input_tokens
            state["messages_trimmed"] = True
            logger.info(
                f"Context trimmed: {len(history_messages)} -> {len(trimmed)} messages"
            )
        else:
            state["messages_trimmed"] = False

    async def after_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
    ) -> None:
        """Record actual token usage from the API response."""
        if context.response is not None:
            usage = getattr(context.response, "usage_details", {})
            if isinstance(usage, dict):
                state["actual_input_tokens"] = usage.get("input_token_count", 0)
                state["actual_output_tokens"] = usage.get("output_token_count", 0)

    def _trim_messages(
        self,
        messages: list[Any],
        budget: int,
        session: Any,
    ) -> list[Any]:
        """Remove oldest messages until history fits within budget.

        Preserves the most recent messages. Also updates the persistent
        session state so trimmed messages don't reappear next turn.

        Args:
            messages: History messages to trim.
            budget: Token budget for history.
            session: The agent session (for persisting the trim).

        Returns:
            Trimmed list of messages.
        """
        if not messages:
            return messages

        # Work backwards from most recent, accumulating until budget
        kept: list[Any] = []
        accumulated = 0
        for msg in reversed(messages):
            msg_tokens = estimate_tokens(_serialize_message(msg))
            if accumulated + msg_tokens > budget:
                break
            kept.append(msg)
            accumulated += msg_tokens

        kept.reverse()

        # Persist the trim in the InMemoryHistoryProvider's state
        in_memory_state = session.state.get("in_memory", {})
        if "messages" in in_memory_state:
            stored = in_memory_state["messages"]
            trim_count = len(messages) - len(kept)
            if trim_count > 0 and len(stored) >= trim_count:
                in_memory_state["messages"] = stored[trim_count:]

        return kept
