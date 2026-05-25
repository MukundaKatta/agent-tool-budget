"""Per-tool call count caps for agent runs.

:class:`ToolBudget` lets you set a maximum number of calls per tool and
tracks consumption.  When a tool is consumed beyond its cap the default
behaviour is to raise :class:`ToolBudgetExceeded`.  You can install a
callback instead if you want soft-limit behaviour.

Example::

    from agent_tool_budget import ToolBudget, ToolBudgetExceeded

    budget = ToolBudget()
    budget.set("search", max_calls=3)
    budget.set("write_file", max_calls=1)

    budget.consume("search")   # 1 / 3
    budget.consume("search")   # 2 / 3
    budget.consume("search")   # 3 / 3  (at limit, not yet exceeded)

    try:
        budget.consume("search")   # raises ToolBudgetExceeded
    except ToolBudgetExceeded as e:
        print(e.tool_name, e.max_calls, e.used)

    print(budget.remaining("search"))      # 0
    print(budget.is_exhausted("search"))   # True
    print(budget.summary())
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


class ToolBudgetExceeded(Exception):
    """Raised when a tool call exceeds its configured budget.

    Attributes:
        tool_name: Name of the tool that was over-consumed.
        max_calls: The configured cap.
        used:      Number of times the tool has been consumed (including the
                   call that triggered this exception).
    """

    def __init__(self, tool_name: str, max_calls: int, used: int) -> None:
        self.tool_name = tool_name
        self.max_calls = max_calls
        self.used = used
        super().__init__(
            f"Tool '{tool_name}' exceeded its budget of {max_calls} calls "
            f"(attempted call #{used})"
        )


@dataclass
class ToolBudgetEntry:
    """Budget configuration and usage for a single tool.

    Attributes:
        tool_name: Name of the tool.
        max_calls: Maximum allowed calls (``None`` = unlimited).
        used:      Number of calls consumed so far.
    """

    tool_name: str
    max_calls: int | None = None
    used: int = 0
    _on_exceed: Callable[[str, int, int], None] | None = field(
        default=None, repr=False
    )

    @property
    def remaining(self) -> int | None:
        """Calls remaining, or ``None`` if unlimited."""
        if self.max_calls is None:
            return None
        return max(0, self.max_calls - self.used)

    @property
    def is_exhausted(self) -> bool:
        """``True`` if the tool has been consumed up to or past its cap."""
        if self.max_calls is None:
            return False
        return self.used >= self.max_calls

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "max_calls": self.max_calls,
            "used": self.used,
            "remaining": self.remaining,
            "is_exhausted": self.is_exhausted,
        }


class ToolBudget:
    """Per-tool call count budget for an agent run.

    Example::

        budget = ToolBudget(default_max=10)   # all tools capped at 10
        budget.set("search", max_calls=3)     # override for search

        budget.consume("search")  # ok
        budget.used("search")     # 1
    """

    def __init__(
        self,
        *,
        default_max: int | None = None,
        on_exceed: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """
        Args:
            default_max: Cap applied to all tools that don't have an explicit
                         ``set()`` call.  ``None`` means unlimited by default.
            on_exceed:   Optional callback ``(tool_name, max_calls, used)``
                         called instead of raising when a tool is over-consumed.
                         If provided, ``consume()`` does NOT raise.
        """
        self._default_max = default_max
        self._on_exceed = on_exceed
        self._entries: dict[str, ToolBudgetEntry] = {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set(
        self,
        tool_name: str,
        *,
        max_calls: int | None,
        on_exceed: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Configure the budget for *tool_name*.

        Args:
            tool_name: Tool to configure.
            max_calls: Maximum allowed calls (``None`` = unlimited for this
                       tool, regardless of *default_max*).
            on_exceed: Per-tool callback, overrides the global one.
        """
        if tool_name in self._entries:
            entry = self._entries[tool_name]
            entry.max_calls = max_calls
            entry._on_exceed = on_exceed
        else:
            self._entries[tool_name] = ToolBudgetEntry(
                tool_name=tool_name,
                max_calls=max_calls,
                _on_exceed=on_exceed,
            )

    def _get_or_create(self, tool_name: str) -> ToolBudgetEntry:
        if tool_name not in self._entries:
            self._entries[tool_name] = ToolBudgetEntry(
                tool_name=tool_name,
                max_calls=self._default_max,
            )
        return self._entries[tool_name]

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def consume(self, tool_name: str) -> None:
        """Record one call to *tool_name*.

        Raises:
            ToolBudgetExceeded: when the cap is exceeded and no ``on_exceed``
                                callback is configured.
        """
        entry = self._get_or_create(tool_name)
        entry.used += 1
        cap = entry.max_calls
        if cap is not None and entry.used > cap:
            # Determine which callback fires
            cb = entry._on_exceed if entry._on_exceed is not None else self._on_exceed
            if cb is not None:
                cb(tool_name, cap, entry.used)
            else:
                raise ToolBudgetExceeded(tool_name, cap, entry.used)

    def check(self, tool_name: str) -> bool:
        """Return ``True`` if consuming *tool_name* one more time is within budget.

        Does NOT increment the counter.
        """
        entry = self._get_or_create(tool_name)
        if entry.max_calls is None:
            return True
        return entry.used < entry.max_calls

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def used(self, tool_name: str) -> int:
        """Number of times *tool_name* has been consumed."""
        return self._get_or_create(tool_name).used

    def remaining(self, tool_name: str) -> int | None:
        """Remaining calls for *tool_name*, or ``None`` if unlimited."""
        return self._get_or_create(tool_name).remaining

    def is_exhausted(self, tool_name: str) -> bool:
        """``True`` if *tool_name* has hit its cap."""
        return self._get_or_create(tool_name).is_exhausted

    def entry(self, tool_name: str) -> ToolBudgetEntry:
        """Return the :class:`ToolBudgetEntry` for *tool_name*."""
        return self._get_or_create(tool_name)

    def all_tools(self) -> list[str]:
        """Sorted list of all tool names that have been configured or consumed."""
        return sorted(self._entries)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all counters (keeps configuration)."""
        for entry in self._entries.values():
            entry.used = 0

    def reset_tool(self, tool_name: str) -> None:
        """Reset the counter for *tool_name* only."""
        if tool_name in self._entries:
            self._entries[tool_name].used = 0

    def clear(self) -> None:
        """Remove all entries (configuration + counters)."""
        self._entries.clear()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a dict with all configured tools and their usage."""
        return {
            "default_max": self._default_max,
            "tools": {name: e.to_dict() for name, e in self._entries.items()},
        }

    def __repr__(self) -> str:
        n = len(self._entries)
        return f"ToolBudget(tools={n}, default_max={self._default_max!r})"
