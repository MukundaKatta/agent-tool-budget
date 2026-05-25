# agent-tool-budget

Per-tool call-count budgets for agent loops. Zero dependencies.

## Install

```bash
pip install agent-tool-budget
```

## Usage

```python
from agent_tool_budget import ToolBudget

budget = ToolBudget({"search": 5, "read_file": 10, "*": 3})

for tool_use in response.tool_uses:
    budget.use(tool_use.name)   # raises BudgetExhausted if over limit
    result = call_tool(tool_use)
```

## Zero dependencies

Standard library only: `dataclasses`. Nothing else.
