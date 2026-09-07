"""
core/config.py — AgentConfig dataclass.

Defines the configuration structure for any agent in the framework.
Adding a new agent = creating a new AgentConfig instance.
"""

from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """Configuration for a single agent persona.

    Attributes:
        name:            Unique agent identifier (matches prompt_key by convention).
        prompt_key:      Key into PROMPT_REGISTRY for this agent's system prompt.
        tool_names:      List of tool name strings this agent is allowed to use.
                         This is enforced at execution time, not merely advertised.
        provider:        Key into PROVIDER_FACTORIES ("deepseek", "openai", "anthropic").
        model:           LLM model identifier, interpreted by the provider.
        max_tokens:      Maximum tokens per LLM response.
        max_iterations:  Safety limit on this agent's own agentic loop.
        delegates_to:    Names of agents this one may hand subtasks to. A non-empty
                         list is what makes an agent an orchestrator — there is no
                         separate flag or subclass. Specialists leave this empty,
                         which is what keeps the topology hub-and-spoke rather than
                         a mesh.
        description:     Human-readable summary. Shown in the UI, and inlined into
                         the orchestrator's delegate tool so it can route correctly.
    """

    name: str
    prompt_key: str
    tool_names: list[str] = field(default_factory=list)
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    max_tokens: int = 1024
    max_iterations: int = 10
    delegates_to: list[str] = field(default_factory=list)
    description: str = ""

    @property
    def is_orchestrator(self) -> bool:
        """True when this agent can delegate to others."""
        return bool(self.delegates_to)
