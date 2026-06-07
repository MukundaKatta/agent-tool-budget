"""Tests for agent-tool-budget.

Standard-library ``unittest`` only — no third-party test dependencies.
Run with::

    python3 -m unittest discover -s tests
"""
import unittest

from agent_tool_budget import (
    BudgetExhausted,
    ToolBudget,
    ToolUsage,
    make_tool_budget,
)


class UseTests(unittest.TestCase):
    def test_use_within_budget(self):
        b = ToolBudget({"search": 3})
        b.use("search")
        b.use("search")
        b.use("search")
        self.assertEqual(b.used("search"), 3)

    def test_use_exhausts_raises(self):
        b = ToolBudget({"search": 2})
        b.use("search")
        b.use("search")
        with self.assertRaises(BudgetExhausted):
            b.use("search")

    def test_use_returns_true(self):
        self.assertIs(ToolBudget({"t": 5}).use("t"), True)

    def test_use_returns_false_no_raise(self):
        b = ToolBudget({"t": 1}, raise_on_exhausted=False)
        b.use("t")
        self.assertIs(b.use("t"), False)

    def test_use_unlimited(self):
        b = ToolBudget()
        for _ in range(100):
            b.use("t")
        self.assertEqual(b.used("t"), 100)

    def test_use_n(self):
        b = ToolBudget({"t": 10})
        b.use("t", n=5)
        self.assertEqual(b.used("t"), 5)

    def test_use_n_zero_raises(self):
        with self.assertRaises(ValueError):
            ToolBudget({"t": 5}).use("t", n=0)

    def test_use_n_negative_raises(self):
        with self.assertRaises(ValueError):
            ToolBudget({"t": 5}).use("t", n=-3)

    def test_use_n_over_limit_in_one_call_raises(self):
        b = ToolBudget({"t": 3})
        with self.assertRaises(BudgetExhausted):
            b.use("t", n=4)

    def test_zero_limit_immediately_exhausted(self):
        b = ToolBudget({"t": 0})
        with self.assertRaises(BudgetExhausted):
            b.use("t")
        self.assertTrue(b.exhausted("t"))
        self.assertEqual(b.remaining("t"), 0)


class ExceptionTests(unittest.TestCase):
    def test_exception_attributes(self):
        b = ToolBudget({"tool": 2})
        b.use("tool")
        b.use("tool")
        try:
            b.use("tool")
            self.fail("expected BudgetExhausted")
        except BudgetExhausted as e:
            self.assertEqual(e.tool_name, "tool")
            self.assertEqual(e.limit, 2)
            self.assertEqual(e.used, 3)

    def test_exception_str(self):
        exc = BudgetExhausted("search", 5, 6)
        self.assertIn("search", str(exc))
        self.assertIn("5", str(exc))

    def test_exception_is_exception(self):
        self.assertIsInstance(BudgetExhausted("t", 1, 2), Exception)


class CheckTests(unittest.TestCase):
    def test_check_within(self):
        self.assertIs(ToolBudget({"t": 3}).check("t"), True)

    def test_check_exhausted(self):
        b = ToolBudget({"t": 2})
        b.use("t")
        b.use("t")
        self.assertIs(b.check("t"), False)

    def test_check_unlimited(self):
        self.assertIs(ToolBudget().check("any"), True)

    def test_check_doesnt_record(self):
        b = ToolBudget({"t": 3})
        b.check("t")
        self.assertEqual(b.used("t"), 0)


class RemainingExhaustedTests(unittest.TestCase):
    def test_remaining_full(self):
        self.assertEqual(ToolBudget({"t": 5}).remaining("t"), 5)

    def test_remaining_after_use(self):
        b = ToolBudget({"t": 5})
        b.use("t")
        b.use("t")
        self.assertEqual(b.remaining("t"), 3)

    def test_remaining_unlimited(self):
        self.assertIsNone(ToolBudget().remaining("t"))

    def test_remaining_never_negative(self):
        b = ToolBudget({"t": 1}, raise_on_exhausted=False)
        b.use("t")
        b.use("t")  # over budget, rejected but recorded
        self.assertEqual(b.remaining("t"), 0)

    def test_exhausted_false(self):
        b = ToolBudget({"t": 3})
        b.use("t")
        self.assertIs(b.exhausted("t"), False)

    def test_exhausted_true(self):
        b = ToolBudget({"t": 2})
        b.use("t")
        b.use("t")
        self.assertIs(b.exhausted("t"), True)

    def test_ok_true(self):
        self.assertIs(ToolBudget({"t": 5}).ok("t"), True)

    def test_ok_false(self):
        b = ToolBudget({"t": 1})
        b.use("t")
        self.assertIs(b.ok("t"), False)


class WildcardDefaultTests(unittest.TestCase):
    def test_wildcard_default(self):
        b = ToolBudget({"*": 2})
        b.use("search")
        b.use("search")
        with self.assertRaises(BudgetExhausted):
            b.use("search")

    def test_explicit_overrides_wildcard(self):
        b = ToolBudget({"search": 10, "*": 2})
        for _ in range(10):
            b.use("search")
        self.assertEqual(b.used("search"), 10)

    def test_wildcard_applies_to_unknown_tools(self):
        b = ToolBudget({"search": 10, "*": 2})
        b.use("other")
        b.use("other")
        with self.assertRaises(BudgetExhausted):
            b.use("other")

    def test_default_limit_param(self):
        b = ToolBudget(default_limit=2)
        b.use("t")
        b.use("t")
        with self.assertRaises(BudgetExhausted):
            b.use("t")

    def test_default_limit_overrides_wildcard(self):
        # explicit default_limit wins over a "*" key in limits
        b = ToolBudget({"*": 5}, default_limit=1)
        b.use("anything")
        with self.assertRaises(BudgetExhausted):
            b.use("anything")

    def test_multiple_tools_independent(self):
        b = ToolBudget({"s": 3, "r": 1})
        b.use("s")
        b.use("s")
        b.use("r")
        with self.assertRaises(BudgetExhausted):
            b.use("r")
        b.use("s")  # still ok
        self.assertEqual(b.used("s"), 3)

    def test_used_unlisted(self):
        self.assertEqual(ToolBudget().used("unknown"), 0)


class ToolUsageTests(unittest.TestCase):
    def test_tool_usage_fields(self):
        b = ToolBudget({"t": 5})
        b.use("t")
        b.use("t")
        u = b.usage("t")
        self.assertEqual(u.used, 2)
        self.assertEqual(u.limit, 5)
        self.assertEqual(u.remaining, 3)
        self.assertFalse(u.exhausted)
        self.assertTrue(u.ok)

    def test_tool_usage_pct(self):
        b = ToolBudget({"t": 10})
        b.use("t")
        b.use("t")
        self.assertAlmostEqual(b.usage("t").pct_used, 0.2)

    def test_tool_usage_pct_unlimited(self):
        b = ToolBudget()
        b.use("t")
        self.assertEqual(b.usage("t").pct_used, 0.0)

    def test_tool_usage_pct_capped_at_one(self):
        b = ToolBudget({"t": 1}, raise_on_exhausted=False)
        b.use("t")
        b.use("t")  # over budget
        self.assertEqual(b.usage("t").pct_used, 1.0)

    def test_tool_usage_unlimited(self):
        b = ToolBudget()
        b.use("t")
        u = b.usage("t")
        self.assertIsNone(u.limit)
        self.assertIsNone(u.remaining)
        self.assertFalse(u.exhausted)

    def test_tool_usage_dataclass_is_instance(self):
        self.assertIsInstance(ToolBudget({"t": 1}).usage("t"), ToolUsage)


class SummaryResetTests(unittest.TestCase):
    def test_summary(self):
        b = ToolBudget({"s": 5})
        b.use("s")
        s = b.summary()
        self.assertEqual(s["s"]["used"], 1)
        self.assertEqual(s["s"]["limit"], 5)
        self.assertEqual(s["s"]["remaining"], 4)
        self.assertFalse(s["s"]["exhausted"])

    def test_summary_empty(self):
        self.assertEqual(ToolBudget({"s": 5}).summary(), {})

    def test_reset_all(self):
        b = ToolBudget({"s": 5, "r": 3})
        b.use("s")
        b.use("r")
        b.reset()
        self.assertEqual(b.used("s"), 0)
        self.assertEqual(b.used("r"), 0)

    def test_reset_specific(self):
        b = ToolBudget({"s": 5, "r": 3})
        b.use("s")
        b.use("r")
        b.reset("s")
        self.assertEqual(b.used("s"), 0)
        self.assertEqual(b.used("r"), 1)

    def test_reset_allows_reuse(self):
        b = ToolBudget({"t": 1})
        b.use("t")
        b.reset()
        b.use("t")  # should not raise
        self.assertEqual(b.used("t"), 1)

    def test_reset_returns_self(self):
        b = ToolBudget({"t": 1})
        self.assertIs(b.reset(), b)


class ValidationAndMiscTests(unittest.TestCase):
    def test_negative_limit_raises(self):
        with self.assertRaises(ValueError):
            ToolBudget({"t": -1})

    def test_negative_default_raises(self):
        with self.assertRaises(ValueError):
            ToolBudget(default_limit=-1)

    def test_make_tool_budget(self):
        b = make_tool_budget(search=5, read_file=10)
        self.assertEqual(b.remaining("search"), 5)
        self.assertEqual(b.remaining("read_file"), 10)

    def test_repr(self):
        self.assertIn("ToolBudget", repr(ToolBudget({"s": 5})))


if __name__ == "__main__":
    unittest.main()
