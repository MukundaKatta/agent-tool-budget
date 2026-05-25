"""Per-tool call-count budget enforcement for agent loops.

Limits how many times each tool can be called in a session.
Different from rate limiting (time-based) — this is a total call count cap.

Zero dependencies — standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class BudgetExhausted(Exception):
    def __init__(self, tool_name: str, limit: int, used: int) -> None:
        self.tool_name = tool_name
        self.limit = limit
        self.used = used
        super().__init__(f"budget exhausted for '{tool_name}': used {used}/{limit} calls")


@dataclass
class ToolUsage:
    tool_name: str
    limit: "int | None"
    used: int

    @property
    def remaining(self) -> "int | None":
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        if self.limit is None:
            return False
        return self.used >= self.limit

    @property
    def ok(self) -> bool:
        return not self.exhausted

    @property
    def pct_used(self) -> float:
        if self.limit is None or self.limit == 0:
            return 0.0
        return min(1.0, self.used / self.limit)


class ToolBudget:
    _WILDCARD = "*"

    def __init__(self, limits=None, *, default_limit=None, raise_on_exhausted=True):
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
            self._default = default_limit
        elif self._WILDCARD in self._limits:
            self._default = self._limits.pop(self._WILDCARD)
        else:
            self._default = None

    def _get_limit(self, tool_name):
        if tool_name in self._limits:
            return self._limits[tool_name]
        return self._default

    def use(self, tool_name, n=1):
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

    def check(self, tool_name):
        limit = self._get_limit(tool_name)
        if limit is None:
            return True
        return self._used.get(tool_name, 0) < limit

    def remaining(self, tool_name):
        limit = self._get_limit(tool_name)
        if limit is None:
            return None
        return max(0, limit - self._used.get(tool_name, 0))

    def used(self, tool_name):
        return self._used.get(tool_name, 0)

    def exhausted(self, tool_name):
        limit = self._get_limit(tool_name)
        if limit is None:
            return False
        return self._used.get(tool_name, 0) >= limit

    def ok(self, tool_name):
        return not self.exhausted(tool_name)

    def usage(self, tool_name):
        return ToolUsage(tool_name=tool_name, limit=self._get_limit(tool_name), used=self._used.get(tool_name, 0))

    def summary(self):
        result = {}
        for name in self._used:
            u = self.usage(name)
            result[name] = {"used": u.used, "limit": u.limit, "remaining": u.remaining, "exhausted": u.exhausted}
        return result

    def reset(self, tool_name=None):
        if tool_name is None:
            self._used.clear()
        else:
            self._used.pop(tool_name, None)
        return self

    def __repr__(self):
        return f"ToolBudget(limits={self._limits}, default={self._default})"


def make_tool_budget(**limits):
    return ToolBudget(limits)
