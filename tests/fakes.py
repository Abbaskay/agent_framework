"""
tests/fakes.py — A scripted LLM provider for tests.

The provider abstraction exists partly for this: swapping in a fake makes the
entire engine — the agentic loop, the allow-list, delegation, budgets — testable
with no network, no API key, and no flakiness.
"""

import json
import uuid

from core.provider import ProviderResponse, ToolCall, register_provider


def say(text: str) -> ProviderResponse:
    """A response where the model is finished and returns text."""
    return ProviderResponse(
        text=text,
        tool_calls=[],
        finish_reason="stop",
        input_tokens=10,
        assistant_message={"role": "assistant", "content": text},
    )


def use_tool(name: str, **arguments) -> ProviderResponse:
    """A response where the model requests one tool call."""
    call_id = f"call_{uuid.uuid4().hex[:8]}"
    return ProviderResponse(
        text="",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
        finish_reason="tool_calls",
        input_tokens=10,
        assistant_message={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
            ],
        },
    )


def delegate(agent_name: str, task: str) -> ProviderResponse:
    """A response where the orchestrator delegates a subtask."""
    return use_tool("delegate", agent_name=agent_name, task=task)


class FakeProvider:
    """Returns pre-scripted responses instead of calling an LLM.

    Two modes:
      - `script`: a flat list consumed in order (single-agent tests).
      - `routes`: {substring of the system prompt: [responses]} — lets one fake
        serve a whole delegation tree, since each agent is identifiable by its
        system prompt.

    Running past the end of a script yields a plain "done" so a test failure
    shows up as a wrong assertion rather than an IndexError.
    """

    def __init__(self, script=None, routes=None):
        self.script = list(script or [])
        self.routes = {k: list(v) for k, v in (routes or {}).items()}
        self.calls = []  # every request received, for assertions

    def complete(self, messages, system, tools, model, max_tokens):
        """Record the request and return the next scripted response."""
        tool_names = [t["function"]["name"] for t in tools]
        self.calls.append(
            {
                "system": system,
                "messages": list(messages),
                "tools": tool_names,
                "model": model,
            }
        )

        if self.routes:
            for marker, responses in self.routes.items():
                if marker.lower() in system.lower():
                    if responses:
                        return responses.pop(0)
                    return say(f"[{marker} script exhausted]")
            return say("[no route matched]")

        if self.script:
            return self.script.pop(0)
        return say("done")

    # -- assertion helpers -------------------------------------------------

    def tools_offered(self, index: int = 0) -> list[str]:
        """Tool names offered to the model on the Nth call."""
        return self.calls[index]["tools"]

    @property
    def call_count(self) -> int:
        """How many completion requests were made in total."""
        return len(self.calls)


def install(fake: FakeProvider, name: str = "fake") -> str:
    """Register `fake` under a provider name and return that name."""
    register_provider(name, lambda: fake)
    return name
