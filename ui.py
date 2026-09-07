"""
ui.py — Streamlit chat interface with agent selector and thinking panel.

Two-column layout:
  Left:  Chat interface with agent selector
  Right: Thinking panel showing tool calls, nested by delegation depth

All business logic lives in core/. This file only handles presentation.
The agent list is read from the AgentRegistry, so adding an agent in `agents/`
makes it appear here with no change to this file.
"""

import json

import streamlit as st

import agents  # noqa: F401  (side-effect import — populates the registry)
from core.context import RunContext
from core.memory import Memory
from core.registry import registry
from core.runner import run_agent

st.set_page_config(
    page_title="Agent Framework",
    page_icon="🧭",
    layout="wide",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main-header { text-align: center; padding: 1rem 0 0.5rem 0; }
    .main-header h1 {
        background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem; font-weight: 700; margin-bottom: 0.15rem;
    }
    .main-header p { color: #94a3b8; font-size: 0.9rem; }

    .welcome-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px; padding: 1.25rem 1.5rem; margin: 0.75rem 0 1rem 0;
        color: #e2e8f0; font-size: 0.88rem; line-height: 1.6;
    }
    .welcome-card strong { color: #a5b4fc; }

    .thinking-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 0.75rem;
        text-align: center;
    }
    .thinking-header h3 { color: #a5b4fc; margin: 0; font-size: 1.1rem; }
    .thinking-header p { color: #64748b; font-size: 0.8rem; margin: 0.25rem 0 0 0; }

    .mode-badge {
        display: inline-block; background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 20px;
        padding: 0.25rem 0.75rem; color: #a5b4fc; font-size: 0.78rem;
        margin-top: 0.25rem;
    }

    #MainMenu, footer, header { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Agent options, built from the registry
# ---------------------------------------------------------------------------
AGENT_NAMES = registry.names()


def label_for(name: str) -> str:
    """Human-friendly dropdown label, marking orchestrators."""
    config = registry.get(name)
    pretty = name.replace("_", " ").title()
    return f"◆ {pretty}" if config.is_orchestrator else pretty


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thinking_steps" not in st.session_state:
    st.session_state.thinking_steps = []
if "memory" not in st.session_state:
    st.session_state.memory = Memory()
if "current_agent" not in st.session_state:
    st.session_state.current_agent = AGENT_NAMES[0]
if "last_status" not in st.session_state:
    st.session_state.last_status = None

col_chat, col_thinking = st.columns([2, 1], gap="large")

# ========================== LEFT COLUMN — CHAT ============================
with col_chat:
    st.markdown(
        """
        <div class="main-header">
            <h1>🧭 Agent Framework</h1>
            <p>Config-driven agents with a delegating orchestrator — one shared engine</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected = st.selectbox(
        "Agent",
        AGENT_NAMES,
        index=AGENT_NAMES.index(st.session_state.current_agent),
        format_func=label_for,
        label_visibility="collapsed",
    )

    # Switching agents resets the conversation — a new persona should not
    # inherit the previous one's history.
    if selected != st.session_state.current_agent:
        st.session_state.current_agent = selected
        st.session_state.messages = []
        st.session_state.thinking_steps = []
        st.session_state.memory = Memory()
        st.session_state.last_status = None
        st.rerun()

    config = registry.get(selected)

    badge = f"{config.description} · {config.provider}/{config.model}"
    st.markdown(f'<div class="mode-badge">{badge}</div>', unsafe_allow_html=True)

    if not st.session_state.messages:
        if config.is_orchestrator:
            roster = "<br>".join(
                f"&nbsp;&nbsp;• <strong>{n.replace('_', ' ').title()}</strong> — {d}"
                for n, d in registry.describe(config.delegates_to)
            )
            st.markdown(
                f"""
                <div class="welcome-card">
                    🧭 <strong>I coordinate a team of specialists.</strong><br><br>
                    Give me something with more than one part and I'll break it up,
                    route each piece to the right specialist, and combine the results.<br><br>
                    <strong>My team:</strong><br>{roster}<br><br>
                    <em>Try: "Research the quick commerce market in India, then calculate
                    the CAGR if it grew from 5000cr to 12000cr over 3 years."</em>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            tools_list = ", ".join(config.tool_names) or "none"
            st.markdown(
                f"""
                <div class="welcome-card">
                    👋 <strong>{config.name.replace('_', ' ').title()}</strong><br><br>
                    {config.description}<br>
                    <strong>Tools:</strong> {tools_list}<br><br>
                    <em>Type a message to get started.</em>
                </div>
                """,
                unsafe_allow_html=True,
            )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Type your message...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        st.session_state.thinking_steps = []

        def on_tool_call(step: dict) -> None:
            """Record each tool call, including those made by delegated specialists."""
            st.session_state.thinking_steps.append(step)

        with st.chat_message("assistant"):
            with st.spinner("Working..."):
                result = run_agent(
                    task=user_input,
                    config=config,
                    memory=st.session_state.memory,
                    on_tool_call=on_tool_call,
                    context=RunContext(),
                    registry=registry,
                )
            st.markdown(result["answer"])

        st.session_state.messages.append(
            {"role": "assistant", "content": result["answer"]}
        )
        st.session_state.last_status = {
            "stop_reason": result["stop_reason"],
            "iterations": result["iterations"],
            "tool_calls": result["tool_call_count"],
        }
        st.rerun()


# ======================== RIGHT COLUMN — THINKING =========================
with col_thinking:
    st.markdown(
        f"""
        <div class="thinking-header">
            <h3>🧠 Agent Thinking</h3>
            <p>{config.name.replace('_', ' ').title()}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status = st.session_state.last_status
    if status:
        if status["stop_reason"] == "completed":
            st.caption(
                f"✅ {status['tool_calls']} tool call(s) · "
                f"{status['iterations']} iteration(s)"
            )
        else:
            # Surface partial/failed runs rather than letting them look complete.
            st.warning(f"Stopped early: {status['stop_reason'].replace('_', ' ')}")

    steps = st.session_state.thinking_steps
    if steps:
        for i, step in enumerate(steps):
            depth = step.get("depth", 0)
            agent = step.get("agent", "")

            if step.get("sub_trace") is not None:
                # A delegation. Its specialist's own calls were already appended
                # to the log above this entry, since the subtask ran to
                # completion before the delegate call returned.
                title = f"🤝 {agent} → {step.get('agent_name')}"
            else:
                title = f"{'│ ' * depth}🔧 {step['tool']}"
                if depth:
                    title += f"  ({agent})"

            with st.expander(title, expanded=(i == len(steps) - 1)):
                st.markdown("**Input:**")
                st.code(json.dumps(step["input"], indent=2, default=str), language="json")
                st.markdown("**Output:**")
                output = str(step["output"])
                st.code(
                    output[:500] + ("..." if len(output) > 500 else ""),
                    language="text",
                )

        if st.button("🗑️ Clear thinking log"):
            st.session_state.thinking_steps = []
            st.rerun()
    else:
        st.caption("Waiting for the agent to act...")
