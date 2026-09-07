"""
core/runner.py — The shared agent orchestration engine.

This is the heart of the framework. It powers every agent regardless of persona,
tools, or provider. The runner never checks *which* config it received — it
simply follows the config's instructions. That is what makes an orchestrator an
ordinary agent that happens to have a `delegate` tool, rather than a special case.
"""

import time

from dotenv import load_dotenv

from core.config import AgentConfig
from core.context import RunContext
from core.logger import logger
from core.memory import Memory
from core.orchestrator import (
    DELEGATE_TOOL_NAME,
    build_delegate_schema,
    execute_delegation,
)
from core.provider import get_provider
from registries.prompt_registry import PROMPT_REGISTRY
from registries.tool_registry import TOOL_REGISTRY, get_schemas

load_dotenv()

# Retry attempts for a failing provider call, with exponential backoff.
MAX_RETRIES = 3


def _result(
    answer: str,
    trace: list,
    iterations: int,
    memory: Memory,
    success: bool,
    stop_reason: str = "completed",
) -> dict:
    """Build the runner's uniform return value."""
    return {
        "answer": answer,
        "trace": trace,
        "iterations": iterations,
        "tool_call_count": memory.tool_call_count,
        "success": success,
        "stop_reason": stop_reason,
    }


def run_agent(
    task: str,
    config: AgentConfig,
    memory: Memory = None,
    on_tool_call=None,
    context: RunContext = None,
    registry=None,
) -> dict:
    """The shared agent engine. Powers every agent in the framework.

    Args:
        task:         The user's input message or subtask description.
        config:       AgentConfig defining this agent's identity and tools.
        memory:       Memory instance (creates a new one if None).
        on_tool_call: Optional callback fn(step: dict) fired after each tool
                      execution, including tools run by delegated specialists.
                      `step` carries tool/input/output/agent/depth.
        context:      RunContext carrying run_id, depth and the shared budget.
                      Created fresh at the root of a run.
        registry:     AgentRegistry used to resolve delegation targets.

    Returns:
        dict with keys:
            answer:          str  — the agent's final text response
            trace:           list — tool calls, with delegations nested
            iterations:      int  — how many LLM calls were made
            tool_call_count: int  — total tools executed
            success:         bool — True if completed normally
            stop_reason:     str  — completed | max_iterations | budget_exhausted
                                    | provider_error | unexpected_finish
    """
    if memory is None:
        memory = Memory()
    if context is None:
        context = RunContext()
    if registry is None:
        from core.registry import registry as default_registry

        registry = default_registry

    memory.add_user_message(task)

    system_prompt = PROMPT_REGISTRY[config.prompt_key]

    # Build this agent's tool surface. The allow-list is the security boundary;
    # the schema list is only what the model is *told* about. They are kept
    # separate on purpose — see the enforcement check in the tool loop below.
    tool_schemas = get_schemas(config.tool_names)
    allowed_tools = set(config.tool_names)

    # An orchestrator gains the synthesized `delegate` tool — but only while it
    # still has depth budget. At the depth limit it keeps its own tools and
    # simply cannot hand off further, which is what terminates the recursion.
    if config.is_orchestrator and context.can_delegate:
        tool_schemas = tool_schemas + [build_delegate_schema(config, registry)]
        allowed_tools.add(DELEGATE_TOOL_NAME)

    provider = get_provider(config.provider)

    iterations = 0
    agent_trace: list = []

    while iterations < config.max_iterations:
        # The budget is shared by reference across the whole delegation tree, so
        # this ceiling is on total work done by the run, not per agent. It is
        # what stops a runaway orchestrator from spending without limit.
        if not context.budget.consume():
            logger.log_error(
                config.name, "budget_exhausted",
                f"Run budget spent after {context.budget.spent} LLM calls",
                iterations, context,
            )
            partial = _last_assistant_text(memory)
            return _result(
                partial or (
                    "I ran out of my processing budget for this request before "
                    "finishing. Here is how far I got — try narrowing the question."
                ),
                agent_trace, iterations, memory, False, "budget_exhausted",
            )

        iterations += 1

        # ------------------------------------------------------------------
        # Call the provider, with exponential backoff on failure
        # ------------------------------------------------------------------
        response = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = provider.complete(
                    messages=memory.get_messages(),
                    system=system_prompt,
                    tools=tool_schemas,
                    model=config.model,
                    max_tokens=config.max_tokens,
                )
                break
            except Exception as e:
                logger.log_error(
                    config.name, type(e).__name__, str(e)[:200], iterations, context
                )
                if attempt < MAX_RETRIES:
                    time.sleep(2**attempt)  # 2s, 4s
                else:
                    return _result(
                        "I'm sorry, I'm having trouble connecting to my AI service. "
                        "Please try again in a moment.",
                        agent_trace, iterations, memory, False, "provider_error",
                    )

        logger.log_llm_call(
            config.name, config.model, iterations,
            response.finish_reason, response.input_tokens, context,
        )

        # ------------------------------------------------------------------
        # CASE A — model is done
        # ------------------------------------------------------------------
        if response.finish_reason == "stop":
            logger.log_agent_complete(
                config.name, iterations, memory.tool_call_count, context
            )
            return _result(
                response.text, agent_trace, iterations, memory, True, "completed"
            )

        # ------------------------------------------------------------------
        # CASE B — model wants to call tools
        # ------------------------------------------------------------------
        if response.finish_reason == "tool_calls":
            memory.messages.append(response.assistant_message)

            for call in response.tool_calls:
                result, sub_trace = _execute_tool(
                    call, config, allowed_tools, registry, context,
                    iterations, on_tool_call,
                )

                step = {
                    "tool": call.name,
                    "input": call.arguments,
                    "output": result,
                    "agent": config.name,
                    "depth": context.depth,
                }
                if call.name == DELEGATE_TOOL_NAME:
                    # Keyed on the tool name, not on whether sub_trace happens
                    # to be non-empty: a specialist that answered without using
                    # any tools is still a delegation, and the trace must say
                    # who it went to. Nesting the child's trace here is what
                    # turns a flat list of calls into a tree the UI can render.
                    step["agent_name"] = call.arguments.get("agent_name")
                    step["sub_trace"] = sub_trace
                agent_trace.append(step)

                if on_tool_call:
                    on_tool_call(step)

                memory.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": str(result)}
                )
                memory.tool_call_count += 1

            memory.trim()
            continue

        # ------------------------------------------------------------------
        # CASE C — unexpected finish reason
        # ------------------------------------------------------------------
        logger.log_error(
            config.name, "unexpected_finish_reason",
            f"Got: {response.finish_reason}", iterations, context,
        )
        return _result(
            response.text or "I wasn't able to complete that request.",
            agent_trace, iterations, memory, False, "unexpected_finish",
        )

    # ----------------------------------------------------------------------
    # Iteration ceiling reached without a final answer
    # ----------------------------------------------------------------------
    logger.log_error(
        config.name, "max_iterations",
        f"Reached {config.max_iterations} iterations without completing",
        iterations, context,
    )
    return _result(
        "I've been working on this for a while but couldn't reach a final answer. "
        "Could you try rephrasing your question?",
        agent_trace, iterations, memory, False, "max_iterations",
    )


def _execute_tool(
    call, config, allowed_tools, registry, context, iterations, on_tool_call,
) -> tuple[str, list]:
    """Execute one tool call, enforcing this agent's allow-list.

    Returns (result_text, sub_trace); sub_trace is non-empty only for delegation.
    """
    # ENFORCEMENT, not advertisement. Membership in the global TOOL_REGISTRY
    # only proves a tool exists somewhere in the framework — not that *this*
    # agent may call it. Restricting the schema list shapes what the model is
    # offered, but a model can still name a tool it was never shown, so the
    # allow-list has to be checked here, at execution. Without this a research
    # specialist could invoke request_refund.
    if call.name not in allowed_tools:
        result = (
            f"Error: Tool '{call.name}' is not available to agent '{config.name}'. "
            f"Available tools: {', '.join(sorted(allowed_tools)) or 'none'}."
        )
        logger.log_error(
            config.name, "tool_not_permitted",
            f"Blocked call to '{call.name}'", iterations, context,
        )
        return result, []

    if call.name == DELEGATE_TOOL_NAME:
        agent_name = call.arguments.get("agent_name", "")
        subtask = call.arguments.get("task", "")
        if not agent_name or not subtask:
            return "Error: delegate requires both 'agent_name' and 'task'.", []

        text, sub_trace = execute_delegation(
            parent_config=config,
            registry=registry,
            context=context,
            agent_name=agent_name,
            task=subtask,
            on_tool_call=on_tool_call,
        )
        logger.log_tool_call(
            config.name, f"delegate->{agent_name}", call.arguments, text, context
        )
        return text, sub_trace

    if call.name not in TOOL_REGISTRY:
        return f"Error: Unknown tool '{call.name}'", []

    try:
        result = TOOL_REGISTRY[call.name](**call.arguments)
    except TypeError as e:
        # Wrong or missing arguments from the model — recoverable, so tell it.
        result = f"Error calling {call.name}: invalid arguments — {e}"
    except Exception as e:
        result = f"Error executing {call.name}: {type(e).__name__} — {e}"

    logger.log_tool_call(config.name, call.name, call.arguments, result, context)
    return result, []


def _last_assistant_text(memory: Memory) -> str:
    """Best-effort recovery of the most recent assistant text, for partial results."""
    for msg in reversed(memory.get_messages()):
        if msg.get("role") == "assistant" and msg.get("content"):
            return str(msg["content"])
    return ""


__all__ = ["run_agent"]
