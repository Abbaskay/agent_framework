"""
core/orchestrator.py — Delegation as a tool.

The framework is hub-and-spoke: an orchestrator decomposes a task, hands each
subtask to a specialist, and composes the results. Specialists never message
each other — they return to the orchestrator and stop.

That shape is deliberate. In a peer-to-peer mesh any agent may message any
other, and the common failure modes are agents ping-ponging agreement, drifting
off-task, and running up unbounded cost with no single owner of the plan. Here
exactly one agent owns the plan, and the call graph is a tree you can draw.

Mechanically, delegation is not a special code path in the engine: it is one
synthesized tool. `run_agent` already accepts a config and returns a dict, so
"delegate" is just a tool whose implementation calls `run_agent` with a
different config.
"""

from core.config import AgentConfig
from core.context import RunContext
from core.logger import logger
from core.registry import AgentRegistry

DELEGATE_TOOL_NAME = "delegate"


def build_delegate_schema(config: AgentConfig, registry: AgentRegistry) -> dict:
    """Build the `delegate` tool schema for an orchestrator.

    The specialist roster is inlined into the description, and the valid agent
    names are an `enum`, so the model is constrained to real targets rather than
    inventing an agent name.
    """
    targets = registry.describe(config.delegates_to)
    roster = "\n".join(f"- {name}: {desc}" for name, desc in targets)

    return {
        "type": "function",
        "function": {
            "name": DELEGATE_TOOL_NAME,
            "description": (
                "Hand a self-contained subtask to a specialist agent and get its "
                "result back. The specialist starts with a blank context and "
                "CANNOT see this conversation, so the task you write must be "
                "complete and standalone — include every detail it needs.\n\n"
                f"Available specialists:\n{roster}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": [name for name, _ in targets],
                        "description": "Which specialist should handle this subtask.",
                    },
                    "task": {
                        "type": "string",
                        "description": (
                            "The complete, standalone subtask description. Assume "
                            "the specialist knows nothing about the wider request."
                        ),
                    },
                },
                "required": ["agent_name", "task"],
            },
        },
    }


def execute_delegation(
    parent_config: AgentConfig,
    registry: AgentRegistry,
    context: RunContext,
    agent_name: str,
    task: str,
    on_tool_call=None,
) -> tuple[str, list]:
    """Run a subtask on a specialist agent.

    Returns:
        (result_text, sub_trace) — the text goes back to the orchestrator as the
        tool result; the sub_trace is nested into the parent's trace so the full
        tree is inspectable afterwards.
    """
    # Imported here rather than at module scope: runner imports this module to
    # build the delegate tool, so a top-level import would be circular.
    from core.memory import Memory
    from core.runner import run_agent

    # A specialist must be one this orchestrator actually declared. Without this
    # the model could name any registered agent and route around its own config.
    if agent_name not in parent_config.delegates_to:
        return (
            f"Error: '{agent_name}' is not a specialist available to "
            f"'{parent_config.name}'. Available: "
            f"{', '.join(parent_config.delegates_to) or 'none'}.",
            [],
        )

    if not registry.has(agent_name):
        return (f"Error: agent '{agent_name}' is not registered.", [])

    logger.log_delegation(parent_config.name, agent_name, task, context)

    child_config = registry.get(agent_name)
    child_context = context.child(parent_config.name)

    # A fresh Memory per specialist is the point of the pattern: each one gets a
    # clean context containing only its own subtask. Sharing the orchestrator's
    # history would leak the whole conversation into every subagent, reintroduce
    # the drift that makes mesh topologies unreliable, and multiply token cost.
    result = run_agent(
        task=task,
        config=child_config,
        memory=Memory(),
        context=child_context,
        registry=registry,
        # Threaded through so a live UI sees the specialist's tool calls as they
        # happen, not only once the whole subtask returns.
        on_tool_call=on_tool_call,
    )

    text = result["answer"]
    if not result["success"]:
        text = f"[{agent_name} did not fully complete this subtask] {text}"

    return text, result["trace"]
