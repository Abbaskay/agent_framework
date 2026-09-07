"""
main.py — CLI entry point.

Run any registered agent in the terminal without the Streamlit UI.
Useful for development, testing, and debugging.

The agent menu is built from the AgentRegistry, so registering a new agent in
`agents/` makes it appear here automatically.
"""

import agents  # noqa: F401  (side-effect import — populates the registry)
from core.context import RunContext
from core.memory import Memory
from core.registry import registry
from core.runner import run_agent


def print_trace(trace: list, indent: int = 1) -> None:
    """Print a tool trace, recursing into delegations to show the tree."""
    pad = "  " * indent
    for step in trace:
        if step.get("sub_trace") is not None:
            print(f"{pad}└─ delegated to {step.get('agent_name')}")
            print_trace(step["sub_trace"], indent + 1)
        else:
            print(f"{pad}• {step['tool']}({step['input']})")


def main():
    """Run the framework in CLI mode."""
    print("=" * 64)
    print("  Agent Framework — CLI")
    print("=" * 64)
    print("\nAvailable agents:")

    for config in registry.all():
        marker = "◆" if config.is_orchestrator else "•"
        print(f"  {marker} {config.name:22s} {config.description}")
    print("\n  ◆ = orchestrator (can delegate to specialists)\n")

    choice = input(f"Choose an agent [{registry.names()[0]}]: ").strip()
    if not choice:
        choice = registry.names()[0]
    if not registry.has(choice):
        print(f"Unknown agent '{choice}'. Falling back to '{registry.names()[0]}'.")
        choice = registry.names()[0]

    config = registry.get(choice)
    memory = Memory()

    print(f"\n✅ Loaded: {config.name}")
    print(f"   Provider: {config.provider} | Model: {config.model}")
    print(f"   Tools: {', '.join(config.tool_names) or 'none'}")
    if config.is_orchestrator:
        print(f"   Delegates to: {', '.join(config.delegates_to)}")
    print("   Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if user_input.lower() in ("exit", "quit"):
            print("\n👋 Goodbye!")
            break
        if not user_input:
            continue

        # A fresh RunContext per turn: each user message gets its own run_id and
        # its own budget, so one expensive turn doesn't starve the next.
        result = run_agent(
            task=user_input,
            config=config,
            memory=memory,
            context=RunContext(),
            registry=registry,
        )

        print(f"\nAgent: {result['answer']}")
        if result["trace"]:
            print("\n  Trace:")
            print_trace(result["trace"])
        print(
            f"\n  [{result['tool_call_count']} tool(s), "
            f"{result['iterations']} iteration(s), "
            f"status: {result['stop_reason']}]\n"
        )


if __name__ == "__main__":
    main()
