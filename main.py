"""
main.py — CLI entry point for the Hyperzod Agent Framework.

Run agents in the terminal without the Streamlit UI.
Useful for development, testing, and debugging.
"""

from core.memory import Memory
from core.runner import run_agent
from configs.hyperzod import HYPERZOD_CONFIG
from configs.standalone import STANDALONE_CONFIG, RESEARCH_CONFIG, ANALYST_CONFIG


CONFIG_MAP = {
    "hyperzod": HYPERZOD_CONFIG,
    "standalone": STANDALONE_CONFIG,
    "research": RESEARCH_CONFIG,
    "analyst": ANALYST_CONFIG,
}


def main():
    """Run the agent framework in CLI mode."""
    print("=" * 60)
    print("  🛵  Hyperzod Agent Framework — CLI Mode")
    print("=" * 60)
    print()
    print("Available modes:")
    for key, cfg in CONFIG_MAP.items():
        print(f"  • {key:12s} — {cfg.description}")
    print()

    # Select mode
    mode = input("Choose mode (hyperzod/standalone/research/analyst): ").strip().lower()
    if mode not in CONFIG_MAP:
        print(f"Unknown mode '{mode}'. Defaulting to 'hyperzod'.")
        mode = "hyperzod"

    config = CONFIG_MAP[mode]
    memory = Memory()

    print(f"\n✅ Loaded: {config.name} ({config.description})")
    print(f"   Model: {config.model} | Tools: {', '.join(config.tool_names)}")
    print(f"   Type 'exit' or 'quit' to stop.\n")

    # Conversation loop
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            print("\n👋 Goodbye!")
            break
        if not user_input:
            continue

        result = run_agent(user_input, config, memory)
        print(f"\nAgent: {result['answer']}")
        print(
            f"  [{result['tool_call_count']} tool(s) used "
            f"in {result['iterations']} iteration(s)]\n"
        )


if __name__ == "__main__":
    main()
