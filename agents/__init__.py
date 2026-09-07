"""
agents/ — Agent definitions.

Importing this package registers every agent into the default AgentRegistry, so
both entry points (main.py, ui.py) and the orchestrator's delegate tool see one
consistent roster. Adding an agent means adding it to a list here — the CLI menu,
the UI dropdown, and the delegation targets all update from that single edit.
"""

from agents.general import GENERAL_AGENTS
from agents.hyperzod import HYPERZOD_AGENTS
from agents.orchestrator import ORCHESTRATOR_AGENTS
from core.registry import registry

# Specialists must be registered before the orchestrator that delegates to them,
# so registry.validate() below can resolve every target.
for _config in [*GENERAL_AGENTS, *HYPERZOD_AGENTS, *ORCHESTRATOR_AGENTS]:
    registry.register(_config)

# Fail loudly at import time on a misconfigured roster (a delegate target that
# doesn't exist, or an agent delegating to itself). Catching this here beats
# discovering it mid-conversation when the model tries to route.
_problems = registry.validate()
if _problems:
    raise ValueError(
        "Invalid agent registry:\n  " + "\n  ".join(_problems)
    )

__all__ = ["registry"]
