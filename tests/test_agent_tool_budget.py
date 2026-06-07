"""Tests for agent-tool-budget."""

import pytest
from agent_tool_budget import BudgetExhausted, ToolBudget, make_tool_budget


def test_use_within_budget():
    b = ToolBudget({"search": 3})
    b.use("search")
    b.use("search")
    b.use("search")
    assert b.used("search") == 3


def test_use_exhausts_raises():
    b = ToolBudget({"search": 2})
    b.use("search")
    b.use("search")
    with pytest.raises(BudgetExhausted):
        b.use("search")


def test_use_returns_true():
    assert ToolBudget({"t": 5}).use("t") is True


def test_use_returns_false_no_raise():
    b = ToolBudget({"t": 1}, raise_on_exhausted=False)
    b.use("t")
    assert b.use("t") is False


def test_denied_use_does_not_consume_budget():
    b = ToolBudget({"t": 1}, raise_on_exhausted=False)
    b.use("t")
    assert b.use("t") is False
    # A denied call must not inflate usage past the limit.
    assert b.used("t") == 1
    assert b.remaining("t") == 0
    assert b.usage("t").used == 1
    assert b.usage("t").pct_used == pytest.approx(1.0)


def test_denied_use_recovers_after_reset():
    b = ToolBudget({"t": 1}, raise_on_exhausted=False)
    b.use("t")
    b.use("t")  # denied, must not count
    b.reset("t")
    assert b.use("t") is True


def test_raised_use_does_not_consume_budget():
    b = ToolBudget({"t": 2})
    b.use("t")
    b.use("t")
    with pytest.raises(BudgetExhausted):
        b.use("t")
    # The blocked call must not be recorded.
    assert b.used("t") == 2
    assert b.remaining("t") == 0


def test_use_n_overflow_no_raise_does_not_consume():
    b = ToolBudget({"t": 5}, raise_on_exhausted=False)
    b.use("t", n=3)
    assert b.use("t", n=4) is False  # would exceed
    assert b.used("t") == 3


def test_use_unlimited():
    b = ToolBudget()
    for _ in range(100):
        b.use("t")
    assert b.used("t") == 100


def test_use_n():
    b = ToolBudget({"t": 10})
    b.use("t", n=5)
    assert b.used("t") == 5


def test_use_n_zero_raises():
    with pytest.raises(ValueError):
        ToolBudget({"t": 5}).use("t", n=0)


def test_exception_attributes():
    b = ToolBudget({"tool": 2})
    b.use("tool")
    b.use("tool")
    try:
        b.use("tool")
        assert False
    except BudgetExhausted as e:
        assert e.tool_name == "tool"
        assert e.limit == 2
        assert e.used == 3


def test_exception_str():
    exc = BudgetExhausted("search", 5, 6)
    assert "search" in str(exc) and "5" in str(exc)


def test_check_within():
    assert ToolBudget({"t": 3}).check("t") is True


def test_check_exhausted():
    b = ToolBudget({"t": 2})
    b.use("t")
    b.use("t")
    assert b.check("t") is False


def test_check_unlimited():
    assert ToolBudget().check("any") is True


def test_check_doesnt_record():
    b = ToolBudget({"t": 3})
    b.check("t")
    assert b.used("t") == 0


def test_remaining_full():
    assert ToolBudget({"t": 5}).remaining("t") == 5


def test_remaining_after_use():
    b = ToolBudget({"t": 5})
    b.use("t")
    b.use("t")
    assert b.remaining("t") == 3


def test_remaining_unlimited():
    assert ToolBudget().remaining("t") is None


def test_exhausted_false():
    b = ToolBudget({"t": 3})
    b.use("t")
    assert b.exhausted("t") is False


def test_exhausted_true():
    b = ToolBudget({"t": 2})
    b.use("t")
    b.use("t")
    assert b.exhausted("t") is True


def test_ok_true():
    assert ToolBudget({"t": 5}).ok("t") is True


def test_ok_false():
    b = ToolBudget({"t": 1})
    b.use("t")
    assert b.ok("t") is False


def test_wildcard_default():
    b = ToolBudget({"*": 2})
    b.use("search")
    b.use("search")
    with pytest.raises(BudgetExhausted):
        b.use("search")


def test_explicit_overrides_wildcard():
    b = ToolBudget({"search": 10, "*": 2})
    for _ in range(10):
        b.use("search")


def test_default_limit_param():
    b = ToolBudget(default_limit=2)
    b.use("t")
    b.use("t")
    with pytest.raises(BudgetExhausted):
        b.use("t")


def test_multiple_tools_independent():
    b = ToolBudget({"s": 3, "r": 1})
    b.use("s")
    b.use("s")
    b.use("r")
    with pytest.raises(BudgetExhausted):
        b.use("r")
    b.use("s")  # still ok


def test_used_unlisted():
    assert ToolBudget().used("unknown") == 0


def test_tool_usage_fields():
    b = ToolBudget({"t": 5})
    b.use("t")
    b.use("t")
    u = b.usage("t")
    assert u.used == 2 and u.limit == 5 and u.remaining == 3 and not u.exhausted


def test_tool_usage_pct():
    b = ToolBudget({"t": 10})
    b.use("t")
    b.use("t")
    assert b.usage("t").pct_used == pytest.approx(0.2)


def test_tool_usage_unlimited():
    b = ToolBudget()
    b.use("t")
    u = b.usage("t")
    assert u.limit is None and u.remaining is None and not u.exhausted


def test_summary():
    b = ToolBudget({"s": 5})
    b.use("s")
    s = b.summary()
    assert s["s"]["used"] == 1 and s["s"]["limit"] == 5


def test_summary_empty():
    assert ToolBudget({"s": 5}).summary() == {}


def test_reset_all():
    b = ToolBudget({"s": 5, "r": 3})
    b.use("s")
    b.use("r")
    b.reset()
    assert b.used("s") == 0 and b.used("r") == 0


def test_reset_specific():
    b = ToolBudget({"s": 5, "r": 3})
    b.use("s")
    b.use("r")
    b.reset("s")
    assert b.used("s") == 0 and b.used("r") == 1


def test_reset_allows_reuse():
    b = ToolBudget({"t": 1})
    b.use("t")
    b.reset()
    b.use("t")


def test_negative_limit_raises():
    with pytest.raises(ValueError):
        ToolBudget({"t": -1})


def test_negative_default_raises():
    with pytest.raises(ValueError):
        ToolBudget(default_limit=-1)


def test_make_tool_budget():
    b = make_tool_budget(search=5, read_file=10)
    assert b.remaining("search") == 5 and b.remaining("read_file") == 10


def test_repr():
    assert "ToolBudget" in repr(ToolBudget({"s": 5}))
