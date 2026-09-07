"""
tools/general_tools.py — General-purpose tool functions.

Three utilities usable by any agent: search_web, calculate, get_current_time.
Each returns a formatted string — tool results are model-facing text, so errors
are returned as readable strings rather than raised. A raised exception would
end the agent's turn; a returned error lets it recover or explain itself.
"""

import ast
import operator
import os
from datetime import datetime
from typing import Annotated

from registries.tool_registry import tool

# ---------------------------------------------------------------------------
# Safe arithmetic evaluation
#
# We deliberately do NOT use eval(). Passing {"__builtins__": {}} is not a
# sandbox — an attacker reaches the interpreter through object internals, e.g.
# ().__class__.__base__.__subclasses__(), and from there to arbitrary imports.
# Instead we parse the expression to an AST and walk it, allowing only literal
# numbers and a fixed set of arithmetic operators. Any other node type is
# rejected before evaluation, so there is nothing to escape from.
# ---------------------------------------------------------------------------

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Guard against expressions that are cheap to type but expensive to evaluate,
# e.g. 9**9**9 would otherwise hang the agent loop.
_MAX_EXPONENT = 1000


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate a whitelisted arithmetic AST node."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"only numeric literals are allowed, got {node.value!r}")
        return node.value

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ValueError(f"operator '{op_type.__name__}' is not allowed")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Pow and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"exponent too large (max {_MAX_EXPONENT})")
        return _BINARY_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"unary operator '{op_type.__name__}' is not allowed")
        return _UNARY_OPS[op_type](_eval_node(node.operand))

    raise ValueError(f"expression element '{type(node).__name__}' is not allowed")


def safe_eval(expression: str) -> float:
    """Evaluate an arithmetic expression without using eval().

    Supports + - * / // % ** and parentheses over numeric literals only.
    Raises ValueError for anything else — names, calls, attributes, subscripts.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"could not parse expression: {e.msg}") from e
    return _eval_node(tree.body)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

_MAX_SEARCH_RESULTS = 5


def _search_tavily(query: str, api_key: str) -> str:
    """Search via Tavily, which returns results already summarized for LLMs."""
    import json
    import urllib.request

    payload = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "max_results": _MAX_SEARCH_RESULTS,
            "include_answer": True,
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.tavily.com/search",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read())

    lines = [f"Search results for '{query}':"]
    if data.get("answer"):
        lines.append(f"\nSummary: {data['answer']}")
    for item in data.get("results", []):
        lines.append(f"\n• {item.get('title', 'Untitled')}")
        lines.append(f"  {item.get('url', '')}")
        if item.get("content"):
            lines.append(f"  {item['content'][:300]}")
    return "\n".join(lines)


def _search_duckduckgo(query: str) -> str:
    """Search via DuckDuckGo. No API key required."""
    from ddgs import DDGS

    results = list(DDGS().text(query, max_results=_MAX_SEARCH_RESULTS))
    if not results:
        return f"No results found for '{query}'."

    lines = [f"Search results for '{query}':"]
    for item in results:
        lines.append(f"\n• {item.get('title', 'Untitled')}")
        lines.append(f"  {item.get('href', '')}")
        if item.get("body"):
            lines.append(f"  {item['body'][:300]}")
    return "\n".join(lines)


@tool(
    description=(
        "Search the web for current information on a given topic. Returns titles, "
        "URLs, and excerpts from real search results. Use this when the user asks "
        "a factual question, wants to look something up, or asks about recent events."
    )
)
def search_web(
    query: Annotated[str, "The search query string."],
) -> str:
    """Search the web and return real results."""
    # Tavily is purpose-built for LLM retrieval, so prefer it when a key exists.
    # DuckDuckGo needs no key, which keeps the repo runnable straight after clone.
    tavily_key = os.getenv("TAVILY_API_KEY")
    try:
        if tavily_key:
            return _search_tavily(query, tavily_key)
        return _search_duckduckgo(query)
    except ImportError:
        return (
            "Search is unavailable: the 'ddgs' package is not installed. "
            "Run `pip install ddgs`, or set TAVILY_API_KEY to use Tavily instead."
        )
    except Exception as e:
        # Network failures must not end the agent's turn — report and let it continue.
        return f"Search failed for '{query}': {type(e).__name__} — {e}"


@tool(
    description=(
        "Evaluate a mathematical expression and return the result. "
        "Supports basic arithmetic: +, -, *, /, //, %, ** and parentheses. "
        "Use this when the user asks to compute something."
    )
)
def calculate(
    expression: Annotated[
        str, "The math expression to evaluate (e.g., '(25 * 4) + 10')."
    ],
) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = safe_eval(expression)
        return f"📊 Calculation: {expression} = {result}"
    except ZeroDivisionError:
        return f"❌ Calculation error for '{expression}': division by zero"
    except ValueError as e:
        return f"❌ Calculation error for '{expression}': {e}"
    except Exception as e:
        return f"❌ Calculation error for '{expression}': {type(e).__name__} — {e}"


@tool(
    description=(
        "Get the current date and time. Use this when the user asks what time "
        "or date it is, or when a calculation depends on today's date."
    )
)
def get_current_time() -> str:
    """Return the current date and time."""
    now = datetime.now()
    return (
        f"🕐 Current date and time:\n"
        f"- **Date:** {now.strftime('%A, %B %d, %Y')}\n"
        f"- **Time:** {now.strftime('%I:%M:%S %p')}\n"
        f"- **ISO:** {now.isoformat()}"
    )
