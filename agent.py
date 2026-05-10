"""
agent.py — Core orchestration loop for the Hyperzod Support Agent.

Implements the agentic reasoning loop using DeepSeek (OpenAI-compatible API):
  1. Send messages + tool schemas to DeepSeek
  2. If DeepSeek responds with text → return it as the final answer
  3. If DeepSeek requests tool calls → execute them, feed results back, and loop
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from prompts import SYSTEM_PROMPT
from tools import (
    TOOL_SCHEMAS,
    escalate_to_human,
    get_eta,
    get_order_status,
    request_refund,
)

# Load environment variables from .env file
load_dotenv()

# Map tool names to their actual Python functions
TOOLS_MAP = {
    "get_order_status": get_order_status,
    "get_eta": get_eta,
    "request_refund": request_refund,
    "escalate_to_human": escalate_to_human,
}

# DeepSeek model to use
MODEL = "deepseek-chat"


def run_agent(messages: list) -> str:
    """
    Run the agentic loop: send messages to DeepSeek, handle tool calls,
    and return the final text response.

    Args:
        messages: Conversation history in OpenAI message format
                  [{"role": "user"/"assistant", "content": "..."}]

    Returns:
        The agent's final text response as a string.
    """

    # Step 1: Initialize the OpenAI-compatible client pointed at DeepSeek's API
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )

    # Build the full message list with the system prompt prepended
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    # Step 2: Enter the agentic loop
    while True:
        # Step 3: Call DeepSeek with tools and conversation history
        response = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        # Extract the assistant's message from the response
        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        print(f"\n🤖 DeepSeek responded | finish_reason: {finish_reason}")

        # Step 4: Check the finish_reason to decide what to do next

        # ---- CASE A: Model is done reasoning and returns a final text answer ----
        if finish_reason == "stop":
            return assistant_message.content or ""

        # ---- CASE B: Model wants to call one or more tools ----
        elif finish_reason == "tool_calls":
            # Step 5: Append the assistant's message (with tool_calls) to the conversation
            # This preserves the conversation flow so DeepSeek can see what it asked for
            full_messages.append(assistant_message)

            # Step 6: Process each tool call in the response
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id

                # Log the tool call for debugging / observability
                print(f"  🔧 Calling tool: {tool_name}")
                print(f"     Args: {tool_args}")

                # Step 7: Execute the tool function with the provided arguments
                if tool_name in TOOLS_MAP:
                    result = TOOLS_MAP[tool_name](**tool_args)
                else:
                    result = f"Error: Unknown tool '{tool_name}'"

                print(f"     ✅ Result: {result[:100]}...")

                # Step 8: Append the tool result as a tool message
                # DeepSeek expects each tool result as a separate message with role "tool"
                full_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result,
                    }
                )

            # Step 9: Continue the loop — DeepSeek will process tool results
            # and either respond with text or call more tools

        # ---- CASE C: Unexpected finish reason ----
        else:
            print(f"  ⚠️ Unexpected finish_reason: {finish_reason}")
            return (
                "I'm sorry, something unexpected happened on my end. "
                "Please try again or contact support directly."
            )
