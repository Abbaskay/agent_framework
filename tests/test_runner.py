"""
tests/test_runner.py — The shared agent engine.

The most important test here is the allow-list: an agent must not be able to
execute a tool it was never granted, even when the model asks for one by name.
"""

import pytest

from core.config import AgentConfig
from core.context import Budget, RunContext
from core.memory import Memory
from core.runner import run_agent
from tests.fakes import FakeProvider, install, say, use_tool


def make_config(**overrides) -> AgentConfig:
    """An analyst-style agent backed by the fake provider."""
    defaults = dict(
        name="test_agent",
        prompt_key="data_analyst",
        tool_names=["calculate"],
        provider="fake",
        model="fake-model",
    )
    defaults.update(overrides)
    return AgentConfig(**defaults)


class TestHappyPath:
    def test_returns_text_when_model_stops(self):
        provider = FakeProvider([say("The answer is 42.")])
        install(provider)

        result = run_agent("what is the answer?", make_config())

        assert result["success"] is True
        assert result["answer"] == "The answer is 42."
        assert result["stop_reason"] == "completed"
        assert result["iterations"] == 1

    def test_executes_a_tool_then_answers(self):
        provider = FakeProvider(
            [use_tool("calculate", expression="(25 * 4) + 10"), say("It's 110.")]
        )
        install(provider)

        result = run_agent("compute it", make_config())

        assert result["success"] is True
        assert result["tool_call_count"] == 1
        assert len(result["trace"]) == 1
        assert result["trace"][0]["tool"] == "calculate"
        assert "110" in result["trace"][0]["output"]

    def test_tool_result_is_fed_back_to_the_model(self):
        provider = FakeProvider(
            [use_tool("calculate", expression="2 + 2"), say("Four.")]
        )
        install(provider)

        run_agent("add", make_config())

        # Second request must contain the tool result message.
        second_call_messages = provider.calls[1]["messages"]
        assert any(m.get("role") == "tool" for m in second_call_messages)

    def test_only_configured_tools_are_offered(self):
        provider = FakeProvider([say("hi")])
        install(provider)

        run_agent("hello", make_config(tool_names=["calculate", "get_current_time"]))

        assert set(provider.tools_offered()) == {"calculate", "get_current_time"}


class TestAllowList:
    """Tool execution is gated on config.tool_names, not the global registry."""

    def test_blocks_a_tool_the_agent_does_not_have(self):
        # The model names a real, registered tool that this agent was never granted.
        provider = FakeProvider(
            [
                use_tool("request_refund", order_id="HZ002", reason="cold food"),
                say("I can't do that."),
            ]
        )
        install(provider)

        result = run_agent("refund me", make_config(tool_names=["calculate"]))

        output = result["trace"][0]["output"]
        assert "not available" in output
        # Crucially, the refund must not have been processed.
        assert "Refund Requested" not in output

    def test_blocked_tool_does_not_mutate_state(self):
        from data.mock_data import ORDERS

        ORDERS["HZ002"]["refund_status"] = "none"
        provider = FakeProvider(
            [
                use_tool("request_refund", order_id="HZ002", reason="test"),
                say("done"),
            ]
        )
        install(provider)

        run_agent("refund", make_config(tool_names=["calculate"]))

        assert ORDERS["HZ002"]["refund_status"] == "none"

    def test_unknown_tool_name_is_reported(self):
        provider = FakeProvider(
            [use_tool("no_such_tool", x=1), say("couldn't do it")]
        )
        install(provider)

        result = run_agent("do it", make_config(tool_names=["no_such_tool"]))

        assert "Unknown tool" in result["trace"][0]["output"]


class TestFailureModes:
    def test_max_iterations_returns_unsuccessful(self):
        # Always asks for a tool, never stops.
        provider = FakeProvider([use_tool("calculate", expression="1+1")] * 10)
        install(provider)

        result = run_agent("loop", make_config(max_iterations=3))

        assert result["success"] is False
        assert result["stop_reason"] == "max_iterations"
        assert result["iterations"] == 3

    def test_budget_exhaustion_stops_the_run(self):
        provider = FakeProvider([use_tool("calculate", expression="1+1")] * 10)
        install(provider)
        context = RunContext(budget=Budget(remaining=2))

        result = run_agent("loop", make_config(max_iterations=99), context=context)

        assert result["success"] is False
        assert result["stop_reason"] == "budget_exhausted"
        assert provider.call_count == 2

    def test_provider_failure_retries_then_gives_up(self):
        class BrokenProvider:
            def __init__(self):
                self.attempts = 0

            def complete(self, **kwargs):
                self.attempts += 1
                raise ConnectionError("network down")

        broken = BrokenProvider()
        install(broken, name="broken")

        result = run_agent("hello", make_config(provider="broken"))

        assert result["success"] is False
        assert result["stop_reason"] == "provider_error"
        assert broken.attempts == 3

    def test_bad_tool_arguments_are_reported_not_raised(self):
        provider = FakeProvider(
            [use_tool("calculate", wrong_kwarg="oops"), say("sorry")]
        )
        install(provider)

        result = run_agent("go", make_config())

        assert "invalid arguments" in result["trace"][0]["output"]


class TestMemory:
    def test_trim_keeps_first_message_and_bounds_length(self):
        memory = Memory(max_messages=5)
        memory.add_user_message("THE ORIGINAL TASK")
        for i in range(20):
            memory.add_assistant_message(f"filler {i}")

        messages = memory.get_messages()
        assert len(messages) == 5
        assert messages[0]["content"] == "THE ORIGINAL TASK"

    def test_trim_never_leaves_an_orphan_tool_message_first(self):
        """A tool result is only valid right after the assistant turn that
        requested it — an orphan at the window start is rejected by the API."""
        memory = Memory(max_messages=3)
        memory.add_user_message("task")
        memory.messages.append({"role": "assistant", "tool_calls": [{"id": "1"}]})
        memory.messages.append({"role": "tool", "tool_call_id": "1", "content": "r1"})
        memory.messages.append({"role": "tool", "tool_call_id": "2", "content": "r2"})
        memory.messages.append({"role": "assistant", "content": "final"})
        memory.trim()

        messages = memory.get_messages()
        assert messages[0]["content"] == "task"
        assert messages[1].get("role") != "tool"
