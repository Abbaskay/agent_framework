"""
tools.py — Tool functions and schemas for the Hyperzod Support Agent.

Contains four callable tools (get_order_status, get_eta, request_refund,
escalate_to_human) and their Anthropic-format schemas for tool calling.
"""

import uuid
from datetime import datetime

from mock_data import ORDERS


# ---------------------------------------------------------------------------
# Tool 1: Get Order Status
# ---------------------------------------------------------------------------
def get_order_status(order_id: str) -> str:
    """Look up an order and return its current status and details."""
    order = ORDERS.get(order_id.upper())
    if not order:
        return f"❌ Order '{order_id}' not found. Please double-check the order ID and try again."

    items_list = ", ".join(order["items"])
    return (
        f"📦 **Order {order['order_id']}**\n"
        f"- **Customer:** {order['customer_name']}\n"
        f"- **Merchant:** {order['merchant_name']}\n"
        f"- **Items:** {items_list}\n"
        f"- **Status:** {order['status'].replace('_', ' ').title()}\n"
        f"- **Total:** ₹{order['total_amount']:.2f}"
    )


# ---------------------------------------------------------------------------
# Tool 2: Get ETA
# ---------------------------------------------------------------------------
def get_eta(order_id: str) -> str:
    """Return the driver name and estimated delivery time for an order."""
    order = ORDERS.get(order_id.upper())
    if not order:
        return f"❌ Order '{order_id}' not found. Please double-check the order ID and try again."

    if order["status"] == "delivered":
        return f"✅ Order {order['order_id']} has already been delivered!"

    if order["status"] == "cancelled":
        return f"🚫 Order {order['order_id']} was cancelled. No ETA available."

    return (
        f"🚚 **ETA for Order {order['order_id']}**\n"
        f"- **Driver:** {order['driver_name']}\n"
        f"- **Estimated arrival:** {order['eta_minutes']} minutes"
    )


# ---------------------------------------------------------------------------
# Tool 3: Request Refund
# ---------------------------------------------------------------------------
def request_refund(order_id: str, reason: str) -> str:
    """Process a refund request for an eligible order."""
    order = ORDERS.get(order_id.upper())
    if not order:
        return f"❌ Order '{order_id}' not found. Please double-check the order ID and try again."

    if not order["refund_eligible"]:
        return (
            f"⚠️ Order {order['order_id']} is not eligible for a refund. "
            f"Refunds are only available for delivered or cancelled orders that meet our policy criteria. "
            f"If you believe this is an error, please ask me to escalate to a human agent."
        )

    if order["refund_status"] == "requested":
        return (
            f"ℹ️ A refund for order {order['order_id']} has already been requested "
            f"and is being processed. You'll be notified once it's complete."
        )

    if order["refund_status"] == "processed":
        return (
            f"✅ A refund for order {order['order_id']} has already been processed. "
            f"The amount of ₹{order['total_amount']:.2f} should reflect in your account shortly."
        )

    # Mark refund as requested
    order["refund_status"] = "requested"
    ref_number = str(uuid.uuid4())[:8].upper()

    return (
        f"✅ **Refund Requested Successfully**\n"
        f"- **Order:** {order['order_id']}\n"
        f"- **Amount:** ₹{order['total_amount']:.2f}\n"
        f"- **Reason:** {reason}\n"
        f"- **Reference:** REF-{ref_number}\n\n"
        f"Your refund will be processed within 3–5 business days."
    )


# ---------------------------------------------------------------------------
# Tool 4: Escalate to Human
# ---------------------------------------------------------------------------
def escalate_to_human(order_id: str, issue_summary: str) -> str:
    """Create a support ticket and escalate the issue to a human agent."""
    ticket = {
        "ticket_id": str(uuid.uuid4()),
        "order_id": order_id.upper(),
        "issue_summary": issue_summary,
        "timestamp": datetime.now().isoformat(),
        "status": "open",
    }

    # Simulate logging the ticket to console
    print("\n" + "=" * 60)
    print("🎫  NEW SUPPORT TICKET CREATED")
    print("=" * 60)
    for key, value in ticket.items():
        print(f"  {key}: {value}")
    print("=" * 60 + "\n")

    return (
        f"🎫 **Your issue has been escalated.**\n"
        f"- **Ticket ID:** {ticket['ticket_id'][:8].upper()}\n"
        f"- **Order:** {ticket['order_id']}\n"
        f"- **Summary:** {issue_summary}\n\n"
        f"A human support agent will follow up with you within **2 hours**. "
        f"You'll receive updates via your registered email and app notifications."
    )


# ---------------------------------------------------------------------------
# Tool Schemas — OpenAI-compatible format (used by DeepSeek API)
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": (
                "Retrieve the current status and details of a Hyperzod order. "
                "Returns the order ID, customer name, merchant, items, current status, "
                "and total amount. Use this when a customer asks about their order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID (e.g., 'HZ001').",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_eta",
            "description": (
                "Get the estimated delivery time and assigned driver for an order. "
                "Use this when a customer asks when their order will arrive or who is delivering it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID (e.g., 'HZ001').",
                    },
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_refund",
            "description": (
                "Submit a refund request for a Hyperzod order. Checks eligibility and processes "
                "the request if valid. Use this when a customer explicitly asks for a refund."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID to refund (e.g., 'HZ002').",
                    },
                    "reason": {
                        "type": "string",
                        "description": "The customer's reason for requesting a refund.",
                    },
                },
                "required": ["order_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": (
                "Escalate an unresolved or complex issue to a human support agent by creating "
                "a support ticket. Use this when the customer's problem cannot be resolved with "
                "the available tools, or when they explicitly request to speak to a human."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The Hyperzod order ID related to the issue.",
                    },
                    "issue_summary": {
                        "type": "string",
                        "description": "A brief summary of the customer's issue for the human agent.",
                    },
                },
                "required": ["order_id", "issue_summary"],
            },
        },
    },
]
