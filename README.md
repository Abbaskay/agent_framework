# 🛵 Hyperzod Agent Framework

A production-grade, config-driven AI agent framework built with Python. Define an agent's identity, tools, and behavior in a single `AgentConfig` dataclass — the shared engine handles everything else. Powered by DeepSeek via the OpenAI-compatible API with full structured logging, exponential backoff retry, and a real-time thinking panel UI.

## Architecture

The framework has 5 layers:

| Layer | Purpose | Files |
|-------|---------|-------|
| **Registries** | Central lookup for tools, schemas, and prompts | `registries/` |
| **Configs** | Agent persona definitions (one dataclass each) | `configs/` |
| **Core Engine** | Shared orchestration loop, memory, logging | `core/` |
| **Tools** | Business logic functions the agent can call | `tools/` |
| **UI** | Streamlit chat interface with thinking panel | `ui.py` |

```
User message → ui.py (Streamlit) → core/runner.py (shared engine)
→ DeepSeek API (reasoning + tool selection) → tools/ (functions) → data/ (mock data)
→ response back up the chain → displayed in UI + logged to agent_logs.jsonl
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env and add your DeepSeek API key from https://platform.deepseek.com/
```

## Run

**Streamlit UI** (recommended):
```bash
streamlit run ui.py
```

**CLI mode** (for development/testing):
```bash
python main.py
```

## Agent Modes

| Mode | Tools | Use Case | Config File |
|------|-------|----------|-------------|
| Hyperzod Support | get_order_status, get_eta, request_refund, escalate_to_human | Customer order support | `configs/hyperzod.py` |
| Standalone Assistant | search_web, calculate, get_current_time | General-purpose helper | `configs/standalone.py` |
| Research Specialist | search_web, get_current_time | Information gathering | `configs/standalone.py` |
| Data Analyst | calculate, get_current_time | Number crunching | `configs/standalone.py` |

## Adding a New Agent (3 Steps)

The framework's core value — adding a new agent requires changes in **exactly 3 places**:

### Step 1: Add tool functions
Create or add functions in `tools/` and register them in `registries/tool_registry.py` and `registries/schema_registry.py`.

### Step 2: Add a system prompt
Add a new entry in `registries/prompt_registry.py` with a unique key.

### Step 3: Add an AgentConfig
Create a new `AgentConfig` in `configs/` referencing the prompt key and tool names.

That's it — the runner, UI, and logging all work automatically.

## Demo Queries

### Hyperzod Support
- `"Where is my order HZ001?"`
- `"I want a refund for order HZ002, the food was cold"`
- `"My order HZ005 has been stuck for hours, this is unacceptable"`

### Standalone Assistant
- `"Search for the latest trends in AI"`
- `"What is 15% of 890?"`
- `"What time is it right now?"`

### Research Specialist
- `"Research the history of quick commerce in India"`
- `"Find information about last-mile delivery optimization"`
- `"What are the latest developments in LLM agents?"`

### Data Analyst
- `"Calculate the compound interest on 50000 at 8% for 3 years"`
- `"What is (1200 * 12) - (350 * 12)?"`
- `"If I save 5000 per month for 2 years, how much do I have?"`

## Project Structure

```
├── core/
│   ├── __init__.py            # Core package
│   ├── runner.py              # Shared agent orchestration engine
│   ├── config.py              # AgentConfig dataclass
│   ├── memory.py              # In-memory conversation manager
│   └── logger.py              # Structured JSONL logging
├── registries/
│   ├── __init__.py            # Registries package
│   ├── tool_registry.py       # Tool name → function mapping
│   ├── schema_registry.py     # Tool name → JSON schema mapping
│   └── prompt_registry.py     # Prompt key → system prompt mapping
├── tools/
│   ├── __init__.py            # Tools package
│   ├── hyperzod_tools.py      # 4 order support tools
│   └── general_tools.py       # 3 general-purpose tools
├── data/
│   └── mock_data.py           # Simulated order database (7 orders)
├── configs/
│   ├── __init__.py            # Configs package
│   ├── hyperzod.py            # Hyperzod support config
│   └── standalone.py          # Standalone, research, analyst configs
├── ui.py                      # Streamlit UI with thinking panel
├── main.py                    # CLI entry point
├── requirements.txt           # Python dependencies
├── .env.example               # API key template
└── README.md                  # This file
```

## Tech Stack

- **Python 3.10+**
- **OpenAI SDK** — DeepSeek (`deepseek-chat`) via OpenAI-compatible API
- **Streamlit** — Two-column chat UI with session state
- **python-dotenv** — Secure API key management
