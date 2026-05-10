"""
tools/general_tools.py — General-purpose tool functions.

Contains 3 utility tools usable by any agent:
search_web, calculate, get_current_time.
Each function returns a formatted string.
"""

from datetime import datetime


def search_web(query: str) -> str:
    """Simulated web search — returns a realistic-looking fake result string."""
    return (
        f"[Web Search Result for '{query}']:\n"
        f"Found several relevant results for \"{query}\".\n"
        f"• Top result: A comprehensive overview of {query} from a reputable source.\n"
        f"• Key finding: The latest information suggests that {query} is a well-documented topic "
        f"with multiple authoritative references available.\n"
        f"• Additional context: Experts in the field have published recent analyses "
        f"covering the main aspects of {query}.\n"
        f"Note: This is a simulated search result for demonstration purposes."
    )


def calculate(expression: str) -> str:
    """Evaluate a mathematical expression and return the result as a string."""
    try:
        # Restrict eval to math-only operations for safety
        result = eval(expression, {"__builtins__": {}}, {})
        return f"📊 Calculation: {expression} = {result}"
    except Exception as e:
        return f"❌ Calculation error for '{expression}': {type(e).__name__} — {e}"


def get_current_time() -> str:
    """Return the current date and time as a formatted string."""
    now = datetime.now()
    return (
        f"🕐 Current date and time:\n"
        f"- **Date:** {now.strftime('%A, %B %d, %Y')}\n"
        f"- **Time:** {now.strftime('%I:%M:%S %p')}\n"
        f"- **ISO:** {now.isoformat()}"
    )
