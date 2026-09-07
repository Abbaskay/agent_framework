"""
core/registry.py — Agent registry.

A single lookup of agent name -> AgentConfig. Previously this mapping was
duplicated in main.py (CONFIG_MAP) and ui.py (MODE_MAP), which meant adding an
agent required editing both entry points and they could silently disagree.
Both now read from here, and the orchestrator uses `describe()` to learn who it
can delegate to.
"""

from core.config import AgentConfig


class AgentRegistry:
    """Name -> AgentConfig lookup with validation."""

    def __init__(self):
        self._agents: dict[str, AgentConfig] = {}

    def register(self, config: AgentConfig) -> AgentConfig:
        """Add an agent. Raises on duplicate names."""
        if config.name in self._agents:
            raise ValueError(f"Agent '{config.name}' is already registered.")
        self._agents[config.name] = config
        return config

    def get(self, name: str) -> AgentConfig:
        """Look up an agent by name. Raises KeyError with the valid options."""
        if name not in self._agents:
            raise KeyError(
                f"Unknown agent '{name}'. Registered: {', '.join(self.names()) or 'none'}"
            )
        return self._agents[name]

    def has(self, name: str) -> bool:
        """True when an agent with this name is registered."""
        return name in self._agents

    def names(self) -> list[str]:
        """All registered agent names, in registration order."""
        return list(self._agents)

    def all(self) -> list[AgentConfig]:
        """Every registered config, in registration order."""
        return list(self._agents.values())

    def describe(self, names: list[str] | None = None) -> list[tuple[str, str]]:
        """Return (name, description) pairs, for UI menus and delegate prompts.

        Args:
            names: Restrict to these agents. Unknown names are skipped rather
                   than raising, so a config listing a not-yet-registered
                   delegate degrades to "can't route there" instead of a crash.
        """
        selected = names if names is not None else self.names()
        return [
            (n, self._agents[n].description) for n in selected if n in self._agents
        ]

    def validate(self) -> list[str]:
        """Check the registry for structural problems.

        Returns a list of human-readable problems (empty when healthy):
          - a delegate target that was never registered
          - an agent listing itself as a delegate (immediate infinite recursion)
        """
        problems = []
        for config in self._agents.values():
            for target in config.delegates_to:
                if target == config.name:
                    problems.append(f"Agent '{config.name}' delegates to itself.")
                elif target not in self._agents:
                    problems.append(
                        f"Agent '{config.name}' delegates to unregistered agent '{target}'."
                    )
        return problems


# Module-level default registry. Agents register themselves into this on import
# of the `agents` package.
registry = AgentRegistry()
