"""
configs/hyperzod.py — Hyperzod customer support agent configuration.
"""

from core.config import AgentConfig

HYPERZOD_CONFIG = AgentConfig(
    name="hyperzod_support",
    prompt_key="hyperzod_support",
    tool_names=["get_order_status", "get_eta", "request_refund", "escalate_to_human"],
    description="Hyperzod customer support agent for order queries",
)
