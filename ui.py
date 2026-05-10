"""
ui.py — Streamlit chat interface with agent mode selector and thinking panel.

Two-column layout:
  Left:  Chat interface with mode selector
  Right: Live thinking panel showing tool calls in real time

All business logic is in core/runner.py — this file only handles presentation.
"""

import json

import streamlit as st

from core.memory import Memory
from core.runner import run_agent
from configs.hyperzod import HYPERZOD_CONFIG
from configs.standalone import STANDALONE_CONFIG, RESEARCH_CONFIG, ANALYST_CONFIG

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Hyperzod Agent Framework",
    page_icon="🛵",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        text-align: center;
        padding: 1rem 0 0.5rem 0;
    }
    .main-header h1 {
        background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.15rem;
    }
    .main-header p {
        color: #94a3b8;
        font-size: 0.9rem;
    }

    .welcome-card {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin: 0.75rem 0 1rem 0;
        color: #e2e8f0;
        font-size: 0.88rem;
        line-height: 1.6;
    }
    .welcome-card strong {
        color: #a5b4fc;
    }

    .thinking-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        text-align: center;
    }
    .thinking-header h3 {
        color: #a5b4fc;
        margin: 0;
        font-size: 1.1rem;
    }
    .thinking-header p {
        color: #64748b;
        font-size: 0.8rem;
        margin: 0.25rem 0 0 0;
    }

    .mode-badge {
        display: inline-block;
        background: rgba(99, 102, 241, 0.15);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 20px;
        padding: 0.25rem 0.75rem;
        color: #a5b4fc;
        font-size: 0.78rem;
        margin-top: 0.25rem;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Mode → Config mapping
# ---------------------------------------------------------------------------
MODE_MAP = {
    "🛵 Hyperzod Support": HYPERZOD_CONFIG,
    "🤖 Standalone Assistant": STANDALONE_CONFIG,
    "🔬 Research Specialist": RESEARCH_CONFIG,
    "📊 Data Analyst": ANALYST_CONFIG,
}

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thinking_steps" not in st.session_state:
    st.session_state.thinking_steps = []
if "memory" not in st.session_state:
    st.session_state.memory = Memory()
if "current_mode" not in st.session_state:
    st.session_state.current_mode = "🛵 Hyperzod Support"

# ---------------------------------------------------------------------------
# Layout: two columns — chat (left) | thinking panel (right)
# ---------------------------------------------------------------------------
col_chat, col_thinking = st.columns([2, 1], gap="large")

# ========================== LEFT COLUMN — CHAT ============================
with col_chat:
    st.markdown(
        """
        <div class="main-header">
            <h1>🛵 Hyperzod Agent Framework</h1>
            <p>Config-driven AI agents — switch modes, same engine</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mode selector
    selected_mode = st.selectbox(
        "Agent Mode",
        list(MODE_MAP.keys()),
        index=list(MODE_MAP.keys()).index(st.session_state.current_mode),
        label_visibility="collapsed",
    )

    # Detect mode change → clear conversation
    if selected_mode != st.session_state.current_mode:
        st.session_state.current_mode = selected_mode
        st.session_state.messages = []
        st.session_state.thinking_steps = []
        st.session_state.memory = Memory()
        st.rerun()

    config = MODE_MAP[selected_mode]

    # Show mode description
    st.markdown(
        f'<div class="mode-badge">{config.description} · Model: {config.model}</div>',
        unsafe_allow_html=True,
    )

    # Welcome message (only when chat is empty)
    if not st.session_state.messages:
        if "Hyperzod" in selected_mode:
            st.markdown(
                """
                <div class="welcome-card">
                    👋 <strong>Hi there! I'm your Hyperzod support assistant.</strong><br><br>
                    I can help you with:<br>
                    • 📦 <strong>Order status</strong> — check what's happening with your order<br>
                    • 🚚 <strong>Delivery ETA</strong> — find out when your order arrives<br>
                    • 💰 <strong>Refunds</strong> — request a refund for eligible orders<br>
                    • 🎫 <strong>Escalation</strong> — connect you with a human agent<br><br>
                    <em>Please share your <strong>order ID</strong> (e.g., HZ001) to get started!</em>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            tools_list = ", ".join(config.tool_names)
            st.markdown(
                f"""
                <div class="welcome-card">
                    👋 <strong>Welcome! I'm your {config.name.replace('_', ' ').title()}.</strong><br><br>
                    {config.description}.<br>
                    <strong>Available tools:</strong> {tools_list}<br><br>
                    <em>Type a message to get started!</em>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Render conversation history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Type your message...")

    if user_input:
        # Display and store user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Define callback for live thinking panel updates
        def on_tool_call(tool_name, tool_input, tool_output):
            """Callback fired after each tool execution."""
            st.session_state.thinking_steps.append(
                {
                    "tool": tool_name,
                    "input": tool_input,
                    "output": tool_output,
                }
            )

        # Call the agent engine
        with st.chat_message("assistant"):
            with st.spinner("Agent is thinking..."):
                result = run_agent(
                    task=user_input,
                    config=config,
                    memory=st.session_state.memory,
                    on_tool_call=on_tool_call,
                )
            st.markdown(result["answer"])

        # Store assistant response
        st.session_state.messages.append(
            {"role": "assistant", "content": result["answer"]}
        )
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

    if st.session_state.thinking_steps:
        for i, step in enumerate(st.session_state.thinking_steps):
            with st.expander(f"🔧 {step['tool']}", expanded=(i == len(st.session_state.thinking_steps) - 1)):
                st.markdown("**Input:**")
                st.code(json.dumps(step["input"], indent=2), language="json")
                st.markdown("**Output:**")
                output_text = step["output"]
                if len(output_text) > 300:
                    output_text = output_text[:300] + "..."
                st.code(output_text, language="text")
    else:
        st.caption("Waiting for agent to act...")

    # Clear thinking log button
    if st.session_state.thinking_steps:
        if st.button("🗑️ Clear thinking log"):
            st.session_state.thinking_steps = []
            st.rerun()
