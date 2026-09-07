"""
core/logger.py — Structured logging for the agent framework.

Logs every LLM call, tool call, delegation, error, and completion to both
console and a JSONL file.

Every event carries run_id / agent / depth / parent, which is what makes a
multi-agent run reconstructable: one `run_id` groups an entire delegation tree,
and depth + parent recover its shape from a flat log file.
"""

import json
from datetime import datetime

from core.context import RunContext


class Logger:
    """Structured logger that writes events to console and a JSONL file."""

    def __init__(self, log_file: str = "agent_logs.jsonl", echo: bool = True):
        """Initialize the logger.

        Args:
            log_file: Target JSONL path.
            echo:     Print to console as well. Tests turn this off.
        """
        self.log_file = log_file
        self.echo = echo

    def log(self, event_type: str, data: dict, context: RunContext | None = None) -> None:
        """Write a structured log entry to file and print to console.

        Args:
            event_type: Category of event (e.g. 'llm_call', 'tool_call').
            data:       Key-value pairs describing the event.
            context:    Run context, contributing run_id / depth / parent.
        """
        timestamp = datetime.now().isoformat()
        entry = {"timestamp": timestamp, "event": event_type, "data": data}

        if context is not None:
            entry["run_id"] = context.run_id
            entry["depth"] = context.depth
            entry["parent"] = context.parent

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            # Logging must never take down an agent run.
            pass

        if self.echo:
            # Indent nested agents so the console shows the tree shape live.
            indent = "  " * (context.depth if context else 0)
            kv_str = " | ".join(f"{k}={v}" for k, v in data.items())
            print(f"{indent}[{timestamp}] [{event_type.upper()}] {kv_str}")

    def log_llm_call(
        self,
        agent_name: str,
        model: str,
        iteration: int,
        stop_reason: str,
        input_tokens: int = 0,
        context: RunContext | None = None,
    ) -> None:
        """Log an LLM API call."""
        self.log(
            "llm_call",
            {
                "agent": agent_name,
                "model": model,
                "iteration": iteration,
                "stop_reason": stop_reason,
                "input_tokens": input_tokens,
            },
            context,
        )

    def log_tool_call(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        context: RunContext | None = None,
    ) -> None:
        """Log a tool function execution. Output truncated to 200 chars."""
        self.log(
            "tool_call",
            {
                "agent": agent_name,
                "tool": tool_name,
                "input": tool_input,
                "output": str(tool_output)[:200],
            },
            context,
        )

    def log_delegation(
        self,
        agent_name: str,
        target_agent: str,
        task: str,
        context: RunContext | None = None,
    ) -> None:
        """Log one agent handing a subtask to another."""
        self.log(
            "delegation",
            {
                "agent": agent_name,
                "target": target_agent,
                "task": task[:200],
            },
            context,
        )

    def log_error(
        self,
        agent_name: str,
        error_type: str,
        message: str,
        iteration: int,
        context: RunContext | None = None,
    ) -> None:
        """Log an error encountered during agent execution."""
        self.log(
            "error",
            {
                "agent": agent_name,
                "error_type": error_type,
                "message": message,
                "iteration": iteration,
            },
            context,
        )

    def log_agent_complete(
        self,
        agent_name: str,
        iterations: int,
        total_tool_calls: int,
        context: RunContext | None = None,
    ) -> None:
        """Log successful completion of an agent run."""
        self.log(
            "agent_complete",
            {
                "agent": agent_name,
                "iterations": iterations,
                "total_tool_calls": total_tool_calls,
                "budget_spent": context.budget.spent if context else None,
            },
            context,
        )


# Module-level singleton — import this everywhere
logger = Logger()
