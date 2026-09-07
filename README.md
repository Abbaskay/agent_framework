# 🧭 Agent Framework

A small, readable multi-agent framework in Python. An **orchestrator** decomposes a task, routes
each subtask to a **specialist agent** from a registry, and composes the results — with a shared
call budget, depth limits, per-agent tool allow-lists, and a structured trace of the whole tree.

Define an agent's identity, tools, and delegation targets in one `AgentConfig`. The shared engine
handles the rest.

```
                    ┌──────────────┐
      user  ───────▶│ ORCHESTRATOR │───────▶  final answer
                    └──────┬───────┘
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        research      data_analyst   hyperzod
       specialist                    support
              │            │            │
              └──────▶ results ◀────────┘
```

**Hub-and-spoke, deliberately.** Specialists report to the orchestrator and stop; they never message
each other. A peer-to-peer mesh — where any agent can talk to any other — demos well once and then
fails in predictable ways: agents ping-pong agreement, drift off-task, and run up unbounded cost with
no single owner of the plan. Here exactly one agent owns the plan and the call graph is a tree.

## Architecture

| Layer | Purpose | Files |
|-------|---------|-------|
| **Core engine** | Agentic loop, delegation, memory, budgets, logging | `core/` |
| **Providers** | Vendor adapters behind one interface | `core/provider.py` |
| **Registries** | Tool functions, schemas, and prompts | `registries/` |
| **Agents** | Persona definitions (one `AgentConfig` each) | `agents/` |
| **Tools** | Functions the agents can call | `tools/` |
| **UI** | Streamlit chat with a nested thinking panel | `ui.py` |

```
user message → ui.py → core/runner.py (shared engine)
    → provider (DeepSeek / OpenAI / Anthropic)
    → tools/  ─── or ───  core/orchestrator.py → run_agent(specialist) ─┐
    ◀────────────────── result + nested trace ◀─────────────────────────┘
```

Delegation is **not** a special path through the engine. `run_agent()` takes a config and returns a
dict, so "delegate to a specialist" is just a synthesized tool whose implementation calls
`run_agent()` with a different config. An orchestrator is an ordinary agent that happens to have a
non-empty `delegates_to`.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then add a key for whichever provider you use
```

## Run

```bash
streamlit run ui.py       # chat UI with the thinking panel
python main.py            # CLI
pytest -q                 # 55 tests, no network or API key needed
```

## Agents

| Agent | Tools | Role |
|-------|-------|------|
| `orchestrator` ◆ | `get_current_time` + `delegate` | Decomposes and routes multi-part requests |
| `research_specialist` | `search_web`, `get_current_time` | Finds and summarizes information |
| `data_analyst` | `calculate`, `get_current_time` | Computes and explains results |
| `standalone_assistant` | all general tools | General-purpose single agent |
| `hyperzod_support` | 4 order tools | Example application pack (see below) |

Try the orchestrator with something that genuinely needs two specialists:

> *"Research the quick commerce market in India, then calculate the CAGR if it grew from 5000 crore
> to 12000 crore over 3 years."*

You'll see it delegate to `research_specialist`, then to `data_analyst`, then synthesize one answer.

## Adding an agent

One file, one `AgentConfig`:

```python
# agents/my_agent.py
from core.config import AgentConfig

WRITER_CONFIG = AgentConfig(
    name="writer",
    prompt_key="writer",              # a key in registries/prompt_registry.py
    tool_names=["search_web"],
    description="Drafts prose from research notes",
)
```

Add it to the list in `agents/__init__.py`. The CLI menu, the UI dropdown, and any orchestrator's
delegation targets all update from that one edit.

## Adding a tool

One decorated function. The JSON schema is derived from the signature, so it cannot drift from the
implementation:

```python
from typing import Annotated
from registries.tool_registry import tool

@tool(description="Look up a customer's loyalty tier.")
def get_loyalty_tier(
    customer_id: Annotated[str, "The customer ID, e.g. 'C-1024'."],
) -> str:
    """Look up a customer's loyalty tier."""
    return f"{customer_id}: Gold"
```

## Swapping providers

`AgentConfig.provider` selects the backend; the engine never imports a vendor SDK directly.

```python
AgentConfig(name="...", provider="anthropic", model="claude-sonnet-5", ...)
```

Built in: `deepseek`, `openai`, `anthropic`. Adding one means a class with a `complete()` method and
an entry in `PROVIDER_FACTORIES` — adapters translate message formats and normalize responses, and
hold no orchestration logic.

## What keeps it bounded

Multi-agent systems fail by running away. Four limits, all enforced in the engine:

- **Tool allow-list** — enforced at *execution*, against `config.tool_names`. Restricting the schema
  list only shapes what the model is offered; a model can still name a tool it was never shown. Without
  the execution check, a research agent could invoke `request_refund`.
- **Shared budget** — one `Budget` object is passed *by reference* through the entire tree, so the
  ceiling is on total LLM calls per run, not per agent. Pass-by-value would hand each subagent a fresh
  allowance and defeat the cap.
- **Depth limit** — at the ceiling an orchestrator keeps its own tools but loses `delegate`, which is
  what terminates the recursion.
- **Bounded memory** — oldest-first trimming that always keeps the originating task and never leaves
  an orphaned tool result at the window start.

Every run gets a `run_id` shared by every agent in its tree; each log line carries `depth` and
`parent`, so a flat `agent_logs.jsonl` reconstructs the tree.

## Tests

```bash
pytest -q     # 55 tests
```

A `FakeProvider` (`tests/fakes.py`) returns scripted responses, so the whole engine — loop,
allow-list, delegation, budgets, memory trimming — is tested with no network and no API key. The
`routes` mode keys scripts by system prompt, which lets one fake serve an entire delegation tree.

## A note on the tools

`search_web` performs **real** searches (DuckDuckGo by default, no key required; Tavily when
`TAVILY_API_KEY` is set). `calculate` is a real AST-based arithmetic evaluator — deliberately not
`eval`, since `eval` with `{"__builtins__": {}}` is escapable via object internals.

The four `hyperzod_*` tools are **fixtures**: they read from an in-memory dict of seven orders in
`data/mock_data.py`, and refund state resets when the process restarts. They exist to give the
framework a realistic multi-tool domain to demonstrate routing against — there is no backend behind
them. `agents/hyperzod.py` is an example application pack; delete it and the framework still runs.

## Project structure

```
├── core/
│   ├── runner.py          # Shared agent engine (the agentic loop)
│   ├── orchestrator.py    # Delegation as a synthesized tool
│   ├── provider.py        # Provider protocol + DeepSeek/OpenAI/Anthropic adapters
│   ├── registry.py        # AgentRegistry
│   ├── context.py         # RunContext + shared Budget
│   ├── config.py          # AgentConfig dataclass
│   ├── memory.py          # Bounded conversation history
│   └── logger.py          # Structured JSONL logging with run_id/depth/parent
├── registries/
│   ├── tool_registry.py   # @tool decorator + schema derivation
│   ├── schema_registry.py # Re-export shim (schemas are now derived)
│   └── prompt_registry.py # System prompts by key
├── agents/
│   ├── orchestrator.py    # The coordinator
│   ├── general.py         # Research, analyst, standalone
│   └── hyperzod.py        # Example application pack
├── tools/
│   ├── general_tools.py   # search_web, calculate, get_current_time
│   └── hyperzod_tools.py  # 4 order-support fixtures
├── data/mock_data.py      # Fixture order database
├── tests/                 # 55 tests + FakeProvider
├── ui.py                  # Streamlit UI
└── main.py                # CLI
```

## Tech stack

Python 3.10+ · OpenAI & Anthropic SDKs · Streamlit · pytest · ddgs
