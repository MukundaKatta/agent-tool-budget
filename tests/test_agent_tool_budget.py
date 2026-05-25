"""Tests for agent_tool_budget."""

from __future__ import annotations

import pytest

from agent_tool_budget import ToolBudget, ToolBudgetEntry, ToolBudgetExceeded

# ---------------------------------------------------------------------------
# ToolBudgetExceeded
# ---------------------------------------------------------------------------


def test_exception_attributes():
    exc = ToolBudgetExceeded("search", 3, 4)
    assert exc.tool_name == "search"
    assert exc.max_calls == 3
    assert exc.used == 4


def test_exception_message():
    exc = ToolBudgetExceeded("search", 3, 4)
    msg = str(exc)
    assert "search" in msg
    assert "3" in msg
    assert "4" in msg


# ---------------------------------------------------------------------------
# ToolBudgetEntry
# ---------------------------------------------------------------------------


def test_entry_defaults():
    e = ToolBudgetEntry(tool_name="t")
    assert e.max_calls is None
    assert e.used == 0
    assert e.remaining is None
    assert e.is_exhausted is False


def test_entry_remaining():
    e = ToolBudgetEntry(tool_name="t", max_calls=5, used=2)
    assert e.remaining == 3


def test_entry_remaining_zero():
    e = ToolBudgetEntry(tool_name="t", max_calls=3, used=3)
    assert e.remaining == 0


def test_entry_is_exhausted_true():
    e = ToolBudgetEntry(tool_name="t", max_calls=3, used=3)
    assert e.is_exhausted is True


def test_entry_is_exhausted_false():
    e = ToolBudgetEntry(tool_name="t", max_calls=3, used=2)
    assert e.is_exhausted is False


def test_entry_unlimited_not_exhausted():
    e = ToolBudgetEntry(tool_name="t", max_calls=None, used=1000)
    assert e.is_exhausted is False
    assert e.remaining is None


def test_entry_to_dict():
    e = ToolBudgetEntry(tool_name="t", max_calls=5, used=2)
    d = e.to_dict()
    assert d["tool_name"] == "t"
    assert d["max_calls"] == 5
    assert d["used"] == 2
    assert d["remaining"] == 3
    assert d["is_exhausted"] is False


# ---------------------------------------------------------------------------
# ToolBudget — empty state
# ---------------------------------------------------------------------------


def test_empty_budget():
    b = ToolBudget()
    assert b.all_tools() == []
    assert b.used("t") == 0
    assert b.remaining("t") is None
    assert b.is_exhausted("t") is False


def test_repr_empty():
    b = ToolBudget()
    r = repr(b)
    assert "tools=0" in r
    assert "default_max=None" in r


# ---------------------------------------------------------------------------
# set / configure
# ---------------------------------------------------------------------------


def test_set_tool():
    b = ToolBudget()
    b.set("search", max_calls=5)
    assert b.remaining("search") == 5
    assert b.used("search") == 0


def test_set_override():
    b = ToolBudget()
    b.set("search", max_calls=5)
    b.set("search", max_calls=10)
    assert b.remaining("search") == 10


def test_set_unlimited():
    b = ToolBudget()
    b.set("search", max_calls=None)
    assert b.remaining("search") is None


def test_all_tools_sorted():
    b = ToolBudget()
    b.set("z", max_calls=1)
    b.set("a", max_calls=1)
    assert b.all_tools() == ["a", "z"]


# ---------------------------------------------------------------------------
# default_max
# ---------------------------------------------------------------------------


def test_default_max():
    b = ToolBudget(default_max=5)
    # Any unconfigured tool gets default_max
    assert b.remaining("new_tool") == 5


def test_default_max_none():
    b = ToolBudget(default_max=None)
    assert b.remaining("new_tool") is None


def test_explicit_set_overrides_default():
    b = ToolBudget(default_max=5)
    b.set("search", max_calls=2)
    assert b.remaining("search") == 2


# ---------------------------------------------------------------------------
# consume
# ---------------------------------------------------------------------------


def test_consume_increments_used():
    b = ToolBudget()
    b.set("t", max_calls=5)
    b.consume("t")
    b.consume("t")
    assert b.used("t") == 2


def test_consume_at_limit_is_ok():
    b = ToolBudget()
    b.set("t", max_calls=3)
    b.consume("t")
    b.consume("t")
    b.consume("t")  # 3rd call — at the limit, still ok
    assert b.used("t") == 3


def test_consume_over_limit_raises():
    b = ToolBudget()
    b.set("t", max_calls=2)
    b.consume("t")
    b.consume("t")
    with pytest.raises(ToolBudgetExceeded) as exc_info:
        b.consume("t")
    assert exc_info.value.tool_name == "t"
    assert exc_info.value.max_calls == 2
    assert exc_info.value.used == 3


def test_consume_unlimited_never_raises():
    b = ToolBudget()
    b.set("t", max_calls=None)
    for _ in range(1000):
        b.consume("t")  # should not raise


def test_consume_default_max():
    b = ToolBudget(default_max=2)
    b.consume("t")
    b.consume("t")
    with pytest.raises(ToolBudgetExceeded):
        b.consume("t")


def test_consume_creates_entry():
    b = ToolBudget()
    b.consume("new_tool")
    assert "new_tool" in b.all_tools()


# ---------------------------------------------------------------------------
# on_exceed callback
# ---------------------------------------------------------------------------


def test_global_on_exceed_callback():
    exceeded = []

    def cb(tool, cap, used):
        exceeded.append((tool, cap, used))

    b = ToolBudget(on_exceed=cb)
    b.set("t", max_calls=1)
    b.consume("t")
    b.consume("t")  # exceeds — calls cb, does NOT raise
    assert len(exceeded) == 1
    assert exceeded[0] == ("t", 1, 2)


def test_per_tool_callback_overrides_global():
    global_calls = []
    tool_calls = []

    b = ToolBudget(on_exceed=lambda t, c, u: global_calls.append(t))
    b.set("t", max_calls=1, on_exceed=lambda t, c, u: tool_calls.append(t))
    b.consume("t")
    b.consume("t")
    assert tool_calls == ["t"]
    assert global_calls == []


def test_no_callback_raises():
    b = ToolBudget()
    b.set("t", max_calls=1)
    b.consume("t")
    with pytest.raises(ToolBudgetExceeded):
        b.consume("t")


def test_callback_called_multiple_times():
    calls = []
    b = ToolBudget(on_exceed=lambda t, c, u: calls.append(u))
    b.set("t", max_calls=1)
    b.consume("t")   # ok
    b.consume("t")   # exceed #1
    b.consume("t")   # exceed #2
    assert calls == [2, 3]


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def test_check_true_when_within_budget():
    b = ToolBudget()
    b.set("t", max_calls=3)
    b.consume("t")
    assert b.check("t") is True


def test_check_false_when_exhausted():
    b = ToolBudget()
    b.set("t", max_calls=2)
    b.consume("t")
    b.consume("t")
    assert b.check("t") is False


def test_check_unlimited_always_true():
    b = ToolBudget()
    b.set("t", max_calls=None)
    for _ in range(100):
        b.consume("t")
    assert b.check("t") is True


def test_check_does_not_consume():
    b = ToolBudget()
    b.set("t", max_calls=3)
    b.check("t")
    assert b.used("t") == 0


# ---------------------------------------------------------------------------
# is_exhausted / remaining
# ---------------------------------------------------------------------------


def test_remaining_decrements():
    b = ToolBudget()
    b.set("t", max_calls=5)
    b.consume("t")
    b.consume("t")
    assert b.remaining("t") == 3


def test_is_exhausted_after_cap():
    b = ToolBudget()
    b.set("t", max_calls=1)
    b.consume("t")
    assert b.is_exhausted("t") is True


def test_remaining_never_negative():
    b = ToolBudget(on_exceed=lambda *a: None)
    b.set("t", max_calls=1)
    b.consume("t")
    b.consume("t")  # over limit, callback fired
    assert b.remaining("t") == 0


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


def test_reset_keeps_config():
    b = ToolBudget()
    b.set("t", max_calls=3)
    b.consume("t")
    b.consume("t")
    b.reset()
    assert b.used("t") == 0
    assert b.remaining("t") == 3


def test_reset_tool():
    b = ToolBudget()
    b.set("a", max_calls=3)
    b.set("b", max_calls=3)
    b.consume("a")
    b.consume("b")
    b.reset_tool("a")
    assert b.used("a") == 0
    assert b.used("b") == 1


def test_clear_removes_entries():
    b = ToolBudget()
    b.set("t", max_calls=3)
    b.consume("t")
    b.clear()
    assert b.all_tools() == []
    assert b.used("t") == 0


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


def test_summary_structure():
    b = ToolBudget(default_max=10)
    b.set("search", max_calls=3)
    b.consume("search")
    d = b.summary()
    assert d["default_max"] == 10
    assert "search" in d["tools"]
    assert d["tools"]["search"]["used"] == 1


def test_summary_empty():
    b = ToolBudget()
    d = b.summary()
    assert d["tools"] == {}


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------


def test_entry_accessor():
    b = ToolBudget()
    b.set("t", max_calls=5)
    b.consume("t")
    e = b.entry("t")
    assert isinstance(e, ToolBudgetEntry)
    assert e.used == 1
    assert e.max_calls == 5


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


def test_repr_with_tools():
    b = ToolBudget(default_max=5)
    b.set("a", max_calls=1)
    b.set("b", max_calls=2)
    r = repr(b)
    assert "tools=2" in r
    assert "default_max=5" in r
