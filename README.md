# agent-tool-budget

Per-tool call-count budgets for agent loops. Cap how many times each tool can be
called in a session, so a misbehaving agent can't loop forever on `search` or
read the same file a hundred times. Zero dependencies, pure standard library.

> This is a **call-count** cap, not a rate limiter. It bounds the *total* number
> of calls per tool for the lifetime of a `ToolBudget` instance — there is no
> time component.

## Install

```bash
pip install agent-tool-budget
```

Requires Python 3.10+.

## Quick start

```python
from agent_tool_budget import BudgetExhausted, ToolBudget

# search can be called 5 times, read_file 10 times,
# and every other tool defaults to 3 (the "*" wildcard).
budget = ToolBudget({"search": 5, "read_file": 10, "*": 3})

while not done:
    tool_use = agent.next_tool_call()
    try:
        budget.use(tool_use.name)        # raises BudgetExhausted if over limit
    except BudgetExhausted as exc:
        # Tell the model it ran out of budget for this tool and let it adapt.
        agent.send_tool_error(tool_use.id, str(exc))
        continue
    result = call_tool(tool_use)
    agent.send_tool_result(tool_use.id, result)
```

### Non-raising style

If you'd rather branch on a boolean than catch an exception, construct the
budget with `raise_on_exhausted=False`. `use()` then returns `True` when the
call fit within budget and `False` when it didn't:

```python
budget = ToolBudget({"search": 5}, raise_on_exhausted=False)

if budget.use("search"):
    do_search()
else:
    print("out of search budget")
```

### Checking before you commit

`check()` reports whether a tool still has budget *without* recording a call —
handy for deciding whether to even attempt a call:

```python
if budget.check("search"):
    budget.use("search")
    do_search()
```

### Inspecting usage

```python
budget = ToolBudget({"search": 5})
budget.use("search")
budget.use("search")

budget.used("search")        # 2
budget.remaining("search")   # 3
budget.exhausted("search")   # False

usage = budget.usage("search")
usage.pct_used               # 0.4
usage.remaining              # 3

budget.summary()
# {"search": {"used": 2, "limit": 5, "remaining": 3, "exhausted": False}}

budget.reset()               # clear all counters (limits are kept)
```

## API

### `ToolBudget(limits=None, *, default_limit=None, raise_on_exhausted=True)`

The main entry point.

- `limits` — a `dict` mapping tool name to its maximum call count. A `"*"` key
  sets the default limit for any tool not listed explicitly. Every limit must be
  `>= 0`.
- `default_limit` — default limit for unlisted tools. Takes precedence over a
  `"*"` entry in `limits`. Must be `>= 0` if provided.
- `raise_on_exhausted` — if `True` (default), `use()` raises `BudgetExhausted`
  when a call would exceed the limit; if `False`, `use()` returns `False`.

A tool with no specific limit and no default is **unlimited**.

| Method | Returns | Description |
| --- | --- | --- |
| `use(tool_name, n=1)` | `bool` | Record `n` calls and enforce the budget. Raises `BudgetExhausted` (or returns `False`) if over limit. Raises `ValueError` if `n < 1`. |
| `check(tool_name)` | `bool` | Whether the tool has budget left, **without** recording a call. |
| `remaining(tool_name)` | `int \| None` | Calls left before exhaustion; `None` if unlimited. |
| `used(tool_name)` | `int` | Calls recorded so far. |
| `exhausted(tool_name)` | `bool` | Whether the tool has hit its limit. |
| `ok(tool_name)` | `bool` | Inverse of `exhausted`. |
| `usage(tool_name)` | `ToolUsage` | A snapshot of the tool's usage. |
| `summary()` | `dict` | Per-tool `used`/`limit`/`remaining`/`exhausted` for every tool that has been used. |
| `reset(tool_name=None)` | `ToolBudget` | Clear one or all counters (limits kept); returns `self` for chaining. |

### `ToolUsage`

An immutable snapshot returned by `ToolBudget.usage()`, with fields
`tool_name`, `limit` (`int | None`), `used` (`int`) and the derived properties
`remaining`, `exhausted`, `ok`, and `pct_used` (0.0–1.0).

### `BudgetExhausted`

Exception raised by `use()` when a call exceeds the limit. Carries
`tool_name`, `limit`, and `used` attributes.

### `make_tool_budget(**limits)`

Keyword-argument convenience constructor:

```python
from agent_tool_budget import make_tool_budget

budget = make_tool_budget(search=5, read_file=10)
```

Equivalent to `ToolBudget({"search": 5, "read_file": 10})`.

## Zero dependencies

Standard library only (`dataclasses`, `typing`). Nothing else.

## Development

Run the test suite with the standard library — no third-party tooling required:

```bash
python -m unittest discover -s tests -v
```

## License

MIT — see [LICENSE](LICENSE).
