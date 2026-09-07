"""
core/memory.py — In-memory conversation manager.

Tracks the message history for a single agent session.
Provides helpers for adding user, assistant, and tool result messages,
plus bounded trimming so long-running or orchestrated sessions cannot
grow their context (and their cost) without limit.
"""

# Default ceiling on retained messages. An orchestrated run multiplies LLM
# calls across a delegation tree, so an unbounded history is a real cost bug,
# not a theoretical one.
DEFAULT_MAX_MESSAGES = 40


class Memory:
    """Conversation history manager with a bounded message window."""

    def __init__(self, max_messages: int = DEFAULT_MAX_MESSAGES):
        """Initialize with an empty message list and zero tool calls.

        Args:
            max_messages: Soft ceiling on retained messages. The first user
                          message is always kept — it carries the task.
        """
        self.messages: list[dict] = []
        self.tool_call_count: int = 0
        self.max_messages = max_messages

    def add_user_message(self, content: str) -> None:
        """Append a user message to the conversation."""
        self.messages.append({"role": "user", "content": content})
        self.trim()

    def add_assistant_message(self, content) -> None:
        """Append an assistant message. Content can be a string or a list of blocks."""
        self.messages.append({"role": "assistant", "content": content})
        self.trim()

    def get_messages(self) -> list:
        """Return a copy of the full message history."""
        return list(self.messages)

    def trim(self) -> None:
        """Drop the oldest messages once the window is exceeded.

        Two invariants make this safe to send back to the API:

        1. The first user message is always retained — it states the task, and
           losing it makes the agent forget what it was asked.
        2. The retained window never *begins* with a "tool" message. A tool
           result is only valid immediately after the assistant message whose
           tool_calls it answers; leaving an orphan there is rejected by the
           OpenAI-compatible API. So we advance the cut past any orphans.
        """
        if len(self.messages) <= self.max_messages:
            return

        head, tail = self.messages[:1], self.messages[1:]
        overflow = len(self.messages) - self.max_messages
        cut = min(overflow, len(tail))

        # Advance the cut until the window no longer opens on an orphaned
        # tool result (or we run out of tail to drop).
        while cut < len(tail) and tail[cut].get("role") == "tool":
            cut += 1

        self.messages = head + tail[cut:]

    def clear(self) -> None:
        """Reset conversation history and tool call counter."""
        self.messages = []
        self.tool_call_count = 0
