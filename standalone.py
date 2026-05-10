"""
configs/standalone.py — General-purpose agent configurations.
"""

from core.config import AgentConfig

STANDALONE_CONFIG = AgentConfig(
    name="standalone_assistant",
    prompt_key="standalone_assistant",
    tool_names=["search_web", "calculate", "get_current_time"],
    description="General purpose standalone assistant",
)

RESEARCH_CONFIG = AgentConfig(
    name="research_specialist",
    prompt_key="research_specialist",
    tool_names=["search_web", "get_current_time"],
    description="Specialist research and summarization agent",
)

ANALYST_CONFIG = AgentConfig(
    name="data_analyst",
    prompt_key="data_analyst",
    tool_names=["calculate", "get_current_time"],
    description="Specialist data analysis and calculation agent",
)
