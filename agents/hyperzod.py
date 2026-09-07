"""
agents/hyperzod.py — Example application pack: Hyperzod order support.

This is a *demonstration* of what an application built on the framework looks
like, not part of the framework itself. Delete this file and the framework still
runs. Its tools read from an in-memory fixture (see tools/hyperzod_tools.py).
"""

from core.config import AgentConfig

HYPERZOD_CONFIG = AgentConfig(
    name="hyperzod_support",
    prompt_key="hyperzod_support",
    tool_names=["get_order_status", "get_eta", "request_refund", "escalate_to_human"],
    description=(
        "Handles Hyperzod customer order queries: order status, delivery ETA, "
        "refunds, and escalation to a human agent. Requires an order ID."
    ),
)

HYPERZOD_AGENTS = [HYPERZOD_CONFIG]
