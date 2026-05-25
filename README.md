# agent-tool-budget

Per-tool call count caps for agent runs. Zero dependencies.

Set independent limits on how many times each tool can be called in a single agent run. Unlike total-call-count caps, this lets you budget each tool separately.

## Install

```bash
pip install agent-tool-budget
```

## Usage

```python
from agent_tool_budget import ToolBudget, ToolBudgetExceeded

budget = ToolBudget()
budget.set("search", max_calls=3)
budget.set("write_file", max_calls=1)

budget.consume("search")   # 1 / 3
budget.consume("search")   # 2 / 3
budget.consume("search")   # 3 / 3

try:
    budget.consume("search")   # raises ToolBudgetExceeded
except ToolBudgetExceeded as e:
    print(e.tool_name)   # "search"
    print(e.max_calls)   # 3
    print(e.used)        # 4

print(budget.remaining("search"))      # 0
print(budget.is_exhausted("search"))   # True
print(budget.check("search"))          # False  (won't raise, just checks)
```

## Default cap for all tools

```python
budget = ToolBudget(default_max=5)  # all tools limited to 5 calls
budget.set("search", max_calls=2)   # override for search
```

## Soft limits (callback instead of exception)

```python
def on_exceed(tool_name, max_calls, used):
    print(f"WARNING: {tool_name} exceeded {max_calls} calls (used {used})")

budget = ToolBudget(on_exceed=on_exceed)
budget.set("search", max_calls=3)
# consume beyond limit → calls on_exceed, does NOT raise

# Per-tool callback (overrides global)
budget.set("write_file", max_calls=1, on_exceed=lambda t, c, u: None)
```

## Inspection

```python
budget.used("search")          # calls consumed
budget.remaining("search")     # calls left (None if unlimited)
budget.is_exhausted("search")  # True if at or past cap
budget.check("search")         # True if one more consume is safe

entry = budget.entry("search")
entry.max_calls  # configured cap
entry.used       # calls consumed
entry.remaining  # calls remaining
```

## Reset

```python
budget.reset()              # reset all counters (keeps config)
budget.reset_tool("search") # reset one tool
budget.clear()              # remove all entries
```

## License

MIT
