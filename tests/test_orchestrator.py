"""
tests/test_orchestrator.py — Hub-and-spoke delegation.

These tests pin the properties that keep multi-agent runs bounded and
debuggable: depth limits, a shared budget, context isolation, and a trace that
records the tree rather than flattening it.
"""

import pytest

from core.config import AgentConfig
from core.context import Budget, RunContext
from core.registry import AgentRegistry
from core.runner import run_agent
from tests.fakes import FakeProvider, delegate, install, say, use_tool


@pytest.fixture
def registry():
    """A three-agent registry: one orchestrator, two specialists."""
    reg = AgentRegistry()
    reg.register(
        AgentConfig(
            name="research_specialist",
            prompt_key="research_specialist",
            tool_names=["search_web"],
            provider="fake",
            description="Researches topics",
        )
    )
    reg.register(
        AgentConfig(
            name="data_analyst",
            prompt_key="data_analyst",
            tool_names=["calculate"],
            provider="fake",
            description="Does arithmetic",
        )
    )
    reg.register(
        AgentConfig(
            name="orchestrator",
            prompt_key="orchestrator",
            tool_names=["get_current_time"],
            provider="fake",
            delegates_to=["research_specialist", "data_analyst"],
            description="Coordinates specialists",
        )
    )
    return reg


class TestDelegateToolConstruction:
    def test_orchestrator_is_offered_the_delegate_tool(self, registry):
        provider = FakeProvider([say("done")])
        install(provider)

        run_agent("hi", registry.get("orchestrator"), registry=registry)

        assert "delegate" in provider.tools_offered()

    def test_specialist_is_not_offered_the_delegate_tool(self, registry):
        provider = FakeProvider([say("done")])
        install(provider)

        run_agent("hi", registry.get("data_analyst"), registry=registry)

        assert "delegate" not in provider.tools_offered()

    def test_delegate_enum_lists_only_declared_specialists(self, registry):
        from core.orchestrator import build_delegate_schema

        schema = build_delegate_schema(registry.get("orchestrator"), registry)
        enum = schema["function"]["parameters"]["properties"]["agent_name"]["enum"]

        assert set(enum) == {"research_specialist", "data_analyst"}
        # The roster is inlined so the model can route on capability, not guesswork.
        assert "Does arithmetic" in schema["function"]["description"]


class TestDelegation:
    def test_delegation_runs_the_specialist_and_returns_its_answer(self, registry):
        provider = FakeProvider(
            routes={
                "Orchestrator": [
                    delegate("data_analyst", "Compute 25 * 4"),
                    say("The result is 100."),
                ],
                "Data Analyst": [say("100")],
            }
        )
        install(provider)

        result = run_agent(
            "what is 25 * 4?", registry.get("orchestrator"), registry=registry
        )

        assert result["success"] is True
        assert result["answer"] == "The result is 100."
        assert result["trace"][0]["tool"] == "delegate"
        assert result["trace"][0]["agent_name"] == "data_analyst"

    def test_specialist_trace_is_nested_not_flattened(self, registry):
        provider = FakeProvider(
            routes={
                "Orchestrator": [
                    delegate("data_analyst", "Compute 25 * 4"),
                    say("It's 110."),
                ],
                "Data Analyst": [
                    use_tool("calculate", expression="(25 * 4) + 10"),
                    say("110"),
                ],
            }
        )
        install(provider)

        result = run_agent("compute", registry.get("orchestrator"), registry=registry)

        step = result["trace"][0]
        assert "sub_trace" in step
        assert step["sub_trace"][0]["tool"] == "calculate"
        assert step["sub_trace"][0]["depth"] == 1

    def test_specialist_gets_a_clean_context(self, registry):
        """The specialist must not see the orchestrator's conversation."""
        provider = FakeProvider(
            routes={
                "Orchestrator": [
                    delegate("data_analyst", "Compute 2 + 2"),
                    say("Four."),
                ],
                "Data Analyst": [say("4")],
            }
        )
        install(provider)

        run_agent(
            "SECRET_ORCHESTRATOR_QUESTION", registry.get("orchestrator"), registry=registry
        )

        analyst_call = next(c for c in provider.calls if "Data Analyst" in c["system"])
        transcript = str(analyst_call["messages"])
        assert "SECRET_ORCHESTRATOR_QUESTION" not in transcript
        assert "Compute 2 + 2" in transcript

    def test_cannot_delegate_to_an_undeclared_agent(self, registry):
        provider = FakeProvider(
            routes={
                "Orchestrator": [
                    delegate("hyperzod_support", "refund something"),
                    say("I can't reach that agent."),
                ]
            }
        )
        install(provider)

        result = run_agent("go", registry.get("orchestrator"), registry=registry)

        assert "not a specialist available" in result["trace"][0]["output"]

    def test_delegate_requires_both_arguments(self, registry):
        provider = FakeProvider(
            routes={
                "Orchestrator": [
                    use_tool("delegate", agent_name="data_analyst"),
                    say("oops"),
                ]
            }
        )
        install(provider)

        result = run_agent("go", registry.get("orchestrator"), registry=registry)

        assert "requires both" in result["trace"][0]["output"]


class TestBounds:
    def test_depth_limit_stops_recursion(self, registry):
        """At the depth ceiling an orchestrator keeps its own tools but loses
        the delegate tool — which is what terminates the tree."""
        provider = FakeProvider([say("done")])
        install(provider)
        context = RunContext(depth=1, max_depth=2)

        run_agent(
            "hi", registry.get("orchestrator"), context=context, registry=registry
        )

        assert "delegate" not in provider.tools_offered()
        assert "get_current_time" in provider.tools_offered()

    def test_budget_is_shared_across_the_whole_tree(self, registry):
        """A subagent must draw from the same budget, not get a fresh one."""
        provider = FakeProvider(
            routes={
                "Orchestrator": [
                    delegate("data_analyst", "compute"),
                    say("done"),
                ],
                "Data Analyst": [say("42")],
            }
        )
        install(provider)
        budget = Budget(remaining=10)

        run_agent(
            "go",
            registry.get("orchestrator"),
            context=RunContext(budget=budget),
            registry=registry,
        )

        # 2 orchestrator calls + 1 specialist call, all from one budget.
        assert budget.spent == 3
        assert budget.remaining == 7

    def test_run_id_is_shared_by_parent_and_child(self, registry):
        context = RunContext()
        child = context.child("orchestrator")

        assert child.run_id == context.run_id
        assert child.depth == context.depth + 1
        assert child.parent == "orchestrator"
        assert child.budget is context.budget  # same object, by reference


class TestRegistryValidation:
    def test_flags_unregistered_delegate_target(self):
        reg = AgentRegistry()
        reg.register(
            AgentConfig(
                name="boss", prompt_key="orchestrator", delegates_to=["ghost"]
            )
        )
        problems = reg.validate()

        assert len(problems) == 1
        assert "ghost" in problems[0]

    def test_flags_self_delegation(self):
        reg = AgentRegistry()
        reg.register(
            AgentConfig(name="boss", prompt_key="orchestrator", delegates_to=["boss"])
        )
        assert "delegates to itself" in reg.validate()[0]

    def test_healthy_registry_has_no_problems(self, registry):
        assert registry.validate() == []

    def test_duplicate_registration_raises(self, registry):
        with pytest.raises(ValueError, match="already registered"):
            registry.register(
                AgentConfig(name="data_analyst", prompt_key="data_analyst")
            )
