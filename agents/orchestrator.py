"""
agents/orchestrator.py — The coordinator agent.

Its only distinguishing feature is a non-empty `delegates_to`. The engine gives
any such agent a synthesized `delegate` tool; nothing else about it is special.

It carries `get_current_time` directly because resolving "this year" is cheaper
inline than as a delegation round-trip. Everything substantive it hands off —
that is the point of the role.
"""

from core.config import AgentConfig

ORCHESTRATOR_CONFIG = AgentConfig(
    name="orchestrator",
    prompt_key="orchestrator",
    tool_names=["get_current_time"],
    delegates_to=["research_specialist", "data_analyst", "hyperzod_support"],
    # Coordination needs more turns than a specialist: one per delegation plus
    # a final synthesis pass.
    max_iterations=12,
    max_tokens=2048,
    description=(
        "Coordinates specialist agents to answer multi-part requests. "
        "Breaks a task into subtasks, routes each to the right specialist, "
        "and composes the results into one answer."
    ),
)

ORCHESTRATOR_AGENTS = [ORCHESTRATOR_CONFIG]
