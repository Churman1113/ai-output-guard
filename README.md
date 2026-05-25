# AgentGuard

**AI Output Safety Engine — The seatbelt between LLMs and your systems**

[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-479%20passed-green)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Churman1113/AgentGuard?style=social)](https://github.com/Churman1113/AgentGuard)

---

## Why AgentGuard?

LLM outputs are unreliable. Missing JSON fields, hallucinated APIs, permission bypasses — any of these can cause production incidents.

AgentGuard provides a **three-layer progressive validation pipeline** (Schema → Semantic → Policy) to catch problems before AI output reaches your systems.

```
LLM Output  ──→  [Schema Guard]  ──→  [Semantic Guard]  ──→  [Policy Guard]  ──→  Safe Output
                  Structure check        Intent detection         Policy rules
                  auto-fix               keyword+regex            YAML DSL engine
```

## Quick Start

### Install

```bash
# Core (Python SDK + CLI)
pip install agentguard

# With semantic enhancement (sentence-transformers)
pip install agentguard[semantic]

# All extras (proxy, API, semantic)
pip install agentguard[all]
```

### Use

```python
from agentguard import Guard
from pydantic import BaseModel

class APIResponse(BaseModel):
    action: str
    target: str

# One-line initialization, all three layers active
guard = Guard(
    schema=APIResponse,          # Schema validation + auto-fix
    semantic=True,               # Dangerous intent detection
    policy="policies/prod.yaml", # Policy rule matching
)

# Validate LLM output
result = guard.validate('{"action": "DROP TABLE users", "target": "*"}')

if result.passed:
    use(result.output)    # Safe to use
elif result.blocked:
    log_and_alert(result) # Blocked — check blocked_by
elif result.was_fixed:
    use(result.output)    # Auto-fixed — review fixes
```

## Three Guard Layers

### 1. Schema Guard — Structure Validation

- Supports Pydantic v2 models and raw JSON Schema
- Auto-fix: enum fuzzy matching (Levenshtein), type coercion, missing field defaults, extra field stripping
- Nested object recursive fixing and array item type coercion
- `<1ms` latency

### 2. Semantic Guard — Intent Detection

- 25 built-in dangerous intents (drop_table, ssh_connect, expose_api_key, etc.)
- Three-level matching: keyword (fastest) → regex → heuristic
- `critical`/`high` → DENY, `medium`/`low` → WARN
- Zero external dependencies

### 3. Policy Guard — Rule Engine

- YAML DSL with 14 operators
- Logical combinators: `all` (AND) / `any` (OR)
- Dot-notation nested field access
- 5 actions: `allow` / `deny` / `warn` / `ask_human` / `modify`

## Policy DSL Example

```yaml
version: "1.0"
defaults:
  on_no_match: allow
  on_error: deny

rules:
  - name: block-db-writes
    priority: 100
    condition:
      all:
        - field: action
          operator: in
          value: [DROP, DELETE, TRUNCATE, ALTER]
        - field: target
          operator: matches
          value: "*users*"
    action: deny
    message: "Database write operations blocked for user tables"

  - name: warn-large-response
    priority: 50
    condition:
      field: response_size
      operator: gt
      value: 1000000
    action: warn
    message: "Large response detected"

  - name: flag-external-ssh
    priority: 80
    condition:
      any:
        - field: target_host
          operator: not_in
          value: [10.0.0.0/8, 172.16.0.0/12]
        - field: protocol
          operator: equals
          value: ssh
    action: ask_human
    message: "SSH to external host requires approval"
```

## CLI Usage

```bash
# Quick validation
agentguard check '{"action": "read", "target": "users"}'

# File validation with policy
agentguard validate response.json --policy prod.yaml -v

# Policy file validation
agentguard policy validate policies/prod.yaml
```

## Distribution

AgentGuard can be used in 5 ways, covering every scenario:

| Form | Use Case | Integration |
|:---|:---|:---|
| **Python SDK** | Agent frameworks (LangChain, AutoGen, etc.) | 2 lines of code |
| **CLI** | CI/CD pipelines, shell scripts | Zero intrusion |
| **MCP Server** | Cursor, Copilot, Claude Code, Windsurf | IDE plugin config |
| **API Proxy** | Any LLM API call (zero code changes) | Set HTTP_PROXY |
| **VS Code Extension** | Editor-native diagnostics | Install from marketplace |

### API Proxy — One-Click Deploy

```bash
# Docker deployment
docker run -d -p 8080:8080 \
  -v $(pwd)/policy.yaml:/policies/policy.yaml \
  -e AGENTGUARD_POLICY=/policies/policy.yaml \
  agentguard/proxy:latest

# Client config (zero code)
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
# All LLM API calls are now validated by AgentGuard
```

## Project Structure

```
agentguard/
├── src/agentguard/
│   ├── guard.py           # Main orchestrator (three-layer pipeline)
│   ├── schema_guard.py    # Schema validation + auto-fix
│   ├── semantic_guard.py  # Intent detection (rules)
│   ├── policy_guard.py    # YAML DSL policy engine
│   ├── result.py          # GuardLevel / CheckResult / GuardResult
│   ├── config.py          # Configuration management
│   ├── errors.py          # Exception hierarchy
│   ├── fix/               # Auto-fix (enum/type/schema recursive)
│   ├── semantic/          # Intent registry + rule matcher
│   ├── policy/            # Policy engine (actions/operators/parser/validator)
│   ├── audit/             # Audit logging
│   ├── cli/               # Typer CLI (Rich formatting)
│   ├── api/               # FastAPI REST API (validate/policy/audit/billing)
│   ├── proxy/             # API Proxy (zero-intrusion LLM safety layer)
│   ├── mcp/               # MCP Server (JSON-RPC 2.0 protocol)
│   └── billing/           # Subscription management (Lemon Squeezy)
├── lsp/                   # VS Code extension (TypeScript)
├── dashboard/             # Web Dashboard (Vue 3 + FastAPI)
├── docs/                  # Architecture, API reference, policy templates
├── examples/              # Demo + policy examples
├── tests/                 # 479+ test cases
├── Dockerfile             # API Proxy Docker image
├── docker-compose.yml     # One-command team deployment
└── pyproject.toml
```

## Roadmap

| Phase | Content | Status |
|:---|:---|:---|
| Phase 1 | Python SDK + CLI + Tests | ✅ Complete |
| Phase 2 | MCP Server (IDE integration) | ✅ Complete |
| Phase 2.5 | Schema Guard Enhancement (nested fix, advanced coercion, matching) | ✅ Complete |
| Phase 3 | API Proxy (zero-intrusion) | ✅ Complete |
| Phase 3b | VS Code Extension (editor diagnostics) | ✅ Complete |
| Phase 4 | Dashboard + PyPI Release + Billing | ✅ Complete |

## Pricing

| Tier | Price | Features |
|:---|:---|:---|
| **Community** | Free | SDK + CLI + MCP + LSP + Basic policies |
| **Team** | $29/month | API Proxy + Dashboard + Team policies + Audit export |
| **Enterprise** | Contact us | SSO/SAML + Custom deployment + SLA + Priority support |

## Support Us

If AgentGuard is useful to you, please give us a ⭐!

[![GitHub Stars](https://img.shields.io/github/stars/Churman1113/AgentGuard?style=social)](https://github.com/Churman1113/AgentGuard)

## License

MIT
