"""
agents/general.py — General-purpose specialist agents.

These are domain-neutral: they ship with the framework rather than with any
particular application.
"""

from core.config import AgentConfig

STANDALONE_CONFIG = AgentConfig(
    name="standalone_assistant",
    prompt_key="standalone_assistant",
    tool_names=["search_web", "calculate", "get_current_time"],
    description="General purpose assistant that can search, calculate, and tell the time",
)

RESEARCH_CONFIG = AgentConfig(
    name="research_specialist",
    prompt_key="research_specialist",
    tool_names=["search_web", "get_current_time"],
    description=(
        "Researches topics using web search and returns a structured, cited summary. "
        "Use for questions about facts, events, markets, or background information."
    ),
)

ANALYST_CONFIG = AgentConfig(
    name="data_analyst",
    prompt_key="data_analyst",
    tool_names=["calculate", "get_current_time"],
    description=(
        "Performs arithmetic and interprets the result in plain language. "
        "Use for any computation: percentages, growth rates, totals, comparisons."
    ),
)

GENERAL_AGENTS = [STANDALONE_CONFIG, RESEARCH_CONFIG, ANALYST_CONFIG]
