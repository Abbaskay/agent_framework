"""
core/context.py — Per-run execution context.

One RunContext is created for a user's request and threaded through the entire
delegation tree. It is what makes a multi-agent run *bounded*: without a shared
budget an orchestrator that keeps delegating has no natural stopping point, and
the failure mode is a hang plus a large bill.
"""

import uuid
from dataclasses import dataclass, field

# An orchestrator plus one layer of specialists. Depth 2 is enough for
# hub-and-spoke; raising it starts to allow the tangled call graphs that make
# multi-agent systems hard to reason about.
DEFAULT_MAX_DEPTH = 2

# Total LLM calls allowed across the whole tree, not per agent.
DEFAULT_BUDGET = 25


@dataclass
class Budget:
    """A mutable call budget shared by reference across an entire run.

    Every agent in the tree decrements the *same* object, so the ceiling is on
    total work done, not work per agent. This is deliberately a mutable object
    rather than an int passed by value — pass-by-value would give each subagent
    a fresh allowance and defeat the cap.
    """

    remaining: int = DEFAULT_BUDGET
    spent: int = 0

    def consume(self) -> bool:
        """Spend one LLM call. Returns False when the budget is exhausted."""
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        self.spent += 1
        return True

    @property
    def exhausted(self) -> bool:
        """True when no calls remain."""
        return self.remaining <= 0


@dataclass
class RunContext:
    """Execution context for one agent invocation within a run.

    Attributes:
        run_id:      Shared by every agent in the tree; groups log lines.
        depth:       0 for the entry-point agent, +1 per delegation hop.
        max_depth:   Hard ceiling on delegation depth.
        budget:      Shared Budget instance (by reference — see Budget).
        parent:      Name of the delegating agent, or None at the root.
    """

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    depth: int = 0
    max_depth: int = DEFAULT_MAX_DEPTH
    budget: Budget = field(default_factory=Budget)
    parent: str | None = None

    def child(self, parent_name: str) -> "RunContext":
        """Derive the context for a delegated subtask.

        Shares run_id and the budget object; increments depth.
        """
        return RunContext(
            run_id=self.run_id,
            depth=self.depth + 1,
            max_depth=self.max_depth,
            budget=self.budget,
            parent=parent_name,
        )

    @property
    def can_delegate(self) -> bool:
        """True when another delegation hop is still within the depth limit."""
        return self.depth + 1 < self.max_depth
