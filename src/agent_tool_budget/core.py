"""Per-tool call-count budget enforcement for agent loops.

Limits how many times each tool can be called in a session.
Different from rate limiting (time-based) — this is a total call count cap.

Zero dependencies — standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class BudgetExhausted(Exception):
    """Raised when a tool is used more times than its configured limit allows.

    Only raised by :meth:`ToolBudget.use` when the budget is constructed with
    ``raise_on_exhausted=True`` (the default). The exception carries the
    offending tool name and the relevant counters so callers can react.

    Attributes:
        tool_name: Name of the tool whose budget was exceeded.
        limit: The configured call-count limit for that tool.
        used: The would-be call count, including the rejected call.
    """

    def __init__(self, tool_name: str, limit: int, used: int) -> None:
        self.tool_name = tool_name
        self.limit = limit
        self.used = used
        super().__init__(
            f"budget exhausted for '{tool_name}': used {used}/{limit} calls"
        )


@dataclass
class ToolUsage:
    """An immutable snapshot of one tool's usage against its budget.

    Returned by :meth:`ToolBudget.usage`. A ``limit`` of ``None`` means the
    tool is unlimited.

    Attributes:
        tool_name: Name of the tool this snapshot describes.
        limit: Configured call-count limit, or ``None`` if unlimited.
        used: Number of calls recorded so far.
    """

    tool_name: str
    limit: Optional[int]
    used: int

    @property
    def remaining(self) -> Optional[int]:
        """Calls left before the budget is exhausted.

        Returns ``None`` for unlimited tools and never returns a negative
        number (it clamps to ``0`` if the tool was driven over budget with
        ``raise_on_exhausted=False``).
        """
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        """``True`` once ``used`` has reached or passed ``limit``.

        Always ``False`` for unlimited tools.
        """
        if self.limit is None:
            return False
        return self.used >= self.limit

    @property
    def ok(self) -> bool:
        """``True`` while the tool still has budget left (the inverse of
        :attr:`exhausted`)."""
        return not self.exhausted

    @property
    def pct_used(self) -> float:
        """Fraction of the budget consumed, in the range ``0.0``–``1.0``.

        Returns ``0.0`` for unlimited or zero-limit tools and clamps to
        ``1.0`` when the tool has been driven over budget.
        """
        if self.limit is None or self.limit == 0:
            return 0.0
        return min(1.0, self.used / self.limit)


class ToolBudget:
    """Tracks and caps how many times each tool may be called.

    Limits are looked up per tool name. A tool with no specific limit falls
    back to the *default* limit, which is either the ``default_limit`` argument
    or a wildcard ``"*"`` entry in ``limits``. If neither is set, unlisted
    tools are unlimited.

    Example:
        >>> budget = ToolBudget({"search": 2, "*": 5})
        >>> budget.use("search")
        True
        >>> budget.remaining("search")
        1
        >>> budget.remaining("read_file")  # falls back to the "*" default
        5

    Args:
        limits: Mapping of tool name to its maximum call count. A ``"*"`` key
            sets the default limit for tools not listed explicitly. Each limit
            must be ``>= 0``.
        default_limit: Default limit for unlisted tools. Takes precedence over
            a ``"*"`` entry in ``limits``. Must be ``>= 0`` if provided.
        raise_on_exhausted: If ``True`` (default), :meth:`use` raises
            :class:`BudgetExhausted` when a call would exceed the limit.
            If ``False``, :meth:`use` returns ``False`` instead.

    Raises:
        ValueError: If any configured limit is negative.
    """

    _WILDCARD = "*"

    def __init__(
        self,
        limits: Optional[dict] = None,
        *,
        default_limit: Optional[int] = None,
        raise_on_exhausted: bool = True,
    ) -> None:
        self._limits: dict = {}
        self._used: dict = {}
        self.raise_on_exhausted = raise_on_exhausted

        if limits:
            for k, v in limits.items():
                if v < 0:
                    raise ValueError(f"limit for '{k}' must be >= 0")
                self._limits[k] = v

        if default_limit is not None:
            if default_limit < 0:
                raise ValueError("default_limit must be >= 0")
            # If a wildcard was also provided, default_limit wins; drop the
            # wildcard so it does not linger in _limits and confuse repr().
            self._limits.pop(self._WILDCARD, None)
            self._default: Optional[int] = default_limit
        elif self._WILDCARD in self._limits:
            self._default = self._limits.pop(self._WILDCARD)
        else:
            self._default = None

    def _get_limit(self, tool_name: str) -> Optional[int]:
        if tool_name in self._limits:
            return self._limits[tool_name]
        return self._default

    def use(self, tool_name: str, n: int = 1) -> bool:
        """Record ``n`` calls to ``tool_name`` and enforce its budget.

        Args:
            tool_name: Name of the tool being called.
            n: Number of calls to record (must be ``>= 1``).

        Returns:
            ``True`` if the calls fit within the budget. If they exceed the
            budget and ``raise_on_exhausted`` is ``False``, returns ``False``.

        Raises:
            ValueError: If ``n < 1``.
            BudgetExhausted: If the calls exceed the budget and
                ``raise_on_exhausted`` is ``True``.
        """
        if n < 1:
            raise ValueError("n must be >= 1")
        limit = self._get_limit(tool_name)
        current = self._used.get(tool_name, 0)
        new_count = current + n
        if limit is not None and new_count > limit:
            self._used[tool_name] = new_count
            if self.raise_on_exhausted:
                raise BudgetExhausted(tool_name, limit, new_count)
            return False
        self._used[tool_name] = new_count
        return True

    def check(self, tool_name: str) -> bool:
        """Return whether ``tool_name`` has budget left, without recording a
        call.

        Useful for deciding whether to attempt a tool call before committing
        to it. Unlimited tools always return ``True``.
        """
        limit = self._get_limit(tool_name)
        if limit is None:
            return True
        return self._used.get(tool_name, 0) < limit

    def remaining(self, tool_name: str) -> Optional[int]:
        """Calls left for ``tool_name`` before its budget is exhausted.

        Returns ``None`` for unlimited tools and never returns a negative
        number.
        """
        limit = self._get_limit(tool_name)
        if limit is None:
            return None
        return max(0, limit - self._used.get(tool_name, 0))

    def used(self, tool_name: str) -> int:
        """Number of calls recorded for ``tool_name`` so far."""
        return self._used.get(tool_name, 0)

    def exhausted(self, tool_name: str) -> bool:
        """Whether ``tool_name`` has reached or exceeded its limit.

        Always ``False`` for unlimited tools.
        """
        limit = self._get_limit(tool_name)
        if limit is None:
            return False
        return self._used.get(tool_name, 0) >= limit

    def ok(self, tool_name: str) -> bool:
        """Whether ``tool_name`` still has budget left (inverse of
        :meth:`exhausted`)."""
        return not self.exhausted(tool_name)

    def usage(self, tool_name: str) -> ToolUsage:
        """Return a :class:`ToolUsage` snapshot for ``tool_name``."""
        return ToolUsage(
            tool_name=tool_name,
            limit=self._get_limit(tool_name),
            used=self._used.get(tool_name, 0),
        )

    def summary(self) -> dict:
        """Return a dict describing every tool that has been used.

        The result maps each used tool name to a dict with ``used``,
        ``limit``, ``remaining`` and ``exhausted`` keys. Tools that have a
        configured limit but have never been called are omitted.
        """
        result = {}
        for name in self._used:
            u = self.usage(name)
            result[name] = {
                "used": u.used,
                "limit": u.limit,
                "remaining": u.remaining,
                "exhausted": u.exhausted,
            }
        return result

    def reset(self, tool_name: Optional[str] = None) -> "ToolBudget":
        """Reset usage counters and return ``self`` for chaining.

        Args:
            tool_name: If given, reset only that tool's counter; otherwise
                reset every tool. Configured limits are left untouched.
        """
        if tool_name is None:
            self._used.clear()
        else:
            self._used.pop(tool_name, None)
        return self

    def __repr__(self) -> str:
        return f"ToolBudget(limits={self._limits}, default={self._default})"


def make_tool_budget(**limits: int) -> ToolBudget:
    """Convenience constructor: ``make_tool_budget(search=5, read_file=10)``.

    Equivalent to ``ToolBudget({"search": 5, "read_file": 10})``. Handy when
    tool names are valid Python identifiers.
    """
    return ToolBudget(limits)
