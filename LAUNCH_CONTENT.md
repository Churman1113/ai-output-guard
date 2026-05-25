# AI Output Guard 发布文案

## Twitter/X

```
🚀 发布了 AI Output Guard — AI 输出安全中间件

LLM 输出不可靠？JSON 缺失、幻觉 API、绕过权限...

AI Output Guard 用三层递进校验（结构→语义→策略）在 AI 输出到达系统前拦截问题

✅ Schema Guard — 自动修复 JSON 错误
✅ Semantic Guard — 33 种危险意图检测
✅ Policy Guard — YAML DSL 策略引擎

pip install ai-output-guard 即可体验

⭐ https://github.com/Churman1113/ai-output-guard
```

## Hacker News

```
标题：Show HN: AI Output Guard — AI output safety middleware for LLMs

正文：

Hey HN! 👋

I've been working on AI Output Guard, an AI output safety middleware that sits between LLMs and your systems.

The problem: LLM outputs are unreliable. JSON missing fields, hallucinated APIs, permission bypasses — any of these can cause production incidents.

The solution: Three-layer progressive validation:

1. Schema Guard — validates structure, auto-fixes enum typos (DELTE → DELETE)
2. Semantic Guard — detects 33 dangerous intents (DROP TABLE, rm -rf, expose_api_key)
3. Policy Guard — YAML DSL with 14 operators for custom rules

```python
from agentguard import Guard
from pydantic import BaseModel

class APIResponse(BaseModel):
    action: str
    target: str

guard = Guard(schema=APIResponse, semantic=True, policy="prod.yaml")
result = guard.validate('{"action": "DROP TABLE users", "target": "*"}')
# → DENY: semantic match dangerous intent "drop_table"
```

Supports 5 distribution forms:
- Python SDK (pip install)
- CLI (CI/CD integration)
- MCP Server (Cursor/Copilot/Claude Code)
- API Proxy (zero code change)
- VS Code Extension (editor diagnostics)

Demo: https://github.com/Churman1113/ai-output-guard

Would love your feedback!
```

## Reddit (r/LocalLLaMA / r/MachineLearning)

```
标题: [Project] AI Output Guard — "The seatbelt between LLMs and your systems"

正文：

Hey everyone! 👋

Built AI Output Guard to solve a real problem I've been facing: LLM outputs are unpredictable and can cause real damage in production.

**What it does:**
Three-layer validation pipeline that intercepts LLM outputs before they reach your systems:

🛡️ Schema Guard — Auto-fixes JSON errors (typos, missing fields, type mismatches)
🛡️ Semantic Guard — Detects 33 dangerous intents (DROP TABLE, execute_shell, expose_api_key...)
🛡️ Policy Guard — YAML DSL for custom compliance rules

**Why three layers?**

Most solutions only handle one layer:
- instructor (13k ⭐) → only Schema
- guardrails-ai (6.9k ⭐) → only content filtering
- NeMo Guardrails → only dialogue control

AI Output Guard's progressive pipeline means:
- If structure is wrong, don't bother checking semantics
- If semantics are dangerous, don't check policies

**Quick demo:**
```python
from agentguard import Guard
guard = Guard(semantic=True, policy="prod.yaml")
result = guard.validate('{"action": "DROP TABLE users"}')
# → Blocked: dangerous intent "drop_table" detected
```

**Install:**
```bash
pip install ai-output-guard
```

GitHub: https://github.com/Churman1113/ai-output-guard

Feedback welcome! 🙏
```

## Buy Me a Coffee / GitHub Sponsors

如果你觉得 AI Output Guard 有帮助：

- GitHub Sponsors: https://github.com/sponsors/Churman1113
- Buy Me a Coffee: https://buymeacoffee.com/ai-output-guard
