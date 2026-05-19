# AgentGuard

**AI 输出安全中间件 — 插在 LLM 和用户之间的安全带**

[![PyPI version](https://img.shields.io/pypi/v/agentguard.svg)](https://pypi.org/project/agentguard/)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-228%20passed-green)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/Churman1113/AgentGuard?style=social)](https://github.com/Churman1113/AgentGuard)

---

## 为什么需要 AgentGuard？

LLM 输出不可靠。JSON 字段缺失、幻觉 API、绕过权限 —— 任何一类问题都可能导致生产事故。

AgentGuard 提供**三层递进校验**（结构 → 语义 → 策略），在 AI 输出到达你的系统之前拦截问题。

```
LLM 输出  ──→  [Schema Guard]  ──→  [Semantic Guard]  ──→  [Policy Guard]  ──→  安全输出
                  结构校验           危险意图检测             策略规则匹配
                  auto-fix           keyword+regex           YAML DSL 引擎
```

## 5 分钟快速开始

### 安装

```bash
# 核心（Python SDK + CLI）
pip install agentguard

# 含语义增强（sentence-transformers）
pip install agentguard[semantic]

# 全部依赖（含异步支持）
pip install agentguard[all]
```

### 快速使用

```python
from agentguard import Guard
from pydantic import BaseModel

class APIResponse(BaseModel):
    action: str
    target: str

# 一行初始化，三层全开
guard = Guard(
    schema=APIResponse,          # 结构校验 + 自动修复
    semantic=True,               # 危险意图检测
    policy="policies/prod.yaml", # 策略规则匹配
)

# 校验 LLM 输出
result = guard.validate('{"action": "DROP TABLE users", "target": "*"}')

if result.passed:
    use(result.output)    # 安全，直接用
elif result.blocked:
    log_and_alert(result) # 被拦截，查看 blocked_by
elif result.was_fixed:
    use(result.output)    # 自动修复了，检查 fixes
```

## 三层 Guard

### 1. Schema Guard — 结构校验

- 支持 Pydantic v2 模型和原始 JSON Schema
- 自动修复：enum 模糊匹配、类型转换、缺失字段填充、多余字段裁剪
- `<1ms` 延迟

### 2. Semantic Guard — 语义检测

- 33 个内置危险意图（drop_table、ssh_connect、expose_api_key 等）
- 三级匹配：keyword（最快）→ regex → heuristic
- `critical`/`high` 直接 DENY，`medium`/`low` 发 WARN
- 零外部依赖

### 3. Policy Guard — 策略引擎

- YAML DSL 定义规则，支持 14 个运算符
- 逻辑组合：`all`(AND) / `any`(OR)
- dot-notation 嵌套字段访问
- 5 种动作：`allow` / `deny` / `warn` / `ask_human` / `modify`

## 策略 DSL 示例

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
```

## CLI 用法

```bash
# 快速校验
agentguard check '{"action": "read", "target": "users"}'

# 文件校验 + 策略
agentguard validate response.json --policy prod.yaml -v

# 策略文件校验
agentguard policy validate policies/prod.yaml
```

## 项目结构

```
agentguard/
├── src/agentguard/
│   ├── guard.py           # Guard 主入口（三层编排）
│   ├── schema_guard.py    # Schema Guard（Pydantic+JSON Schema + 自动修复）
│   ├── semantic_guard.py  # Semantic Guard（规则匹配）
│   ├── policy_guard.py    # Policy Guard（YAML DSL 引擎）
│   ├── result.py          # GuardLevel / CheckResult / GuardResult
│   ├── config.py          # 配置管理
│   ├── errors.py          # 统一异常体系
│   ├── fix/               # 自动修复（enum/type/schema 递归嵌套）
│   ├── semantic/          # 意图注册表 + 规则匹配器
│   ├── policy/            # 策略引擎（actions/operators/parser/validator）
│   ├── audit/             # 审计日志
│   ├── cli/               # Typer CLI（Rich 格式化）
│   ├── api/               # FastAPI REST API（validate/policy/audit）
│   ├── proxy/             # API Proxy（零侵入 LLM 安全层）
│   ├── mcp/               # MCP Server（JSON-RPC 2.0 协议）
│   └── billing/           # 计费系统（可选）
├── docs/                  # 产品定义 / 架构 / API / 策略模板 / 协议流程 / 评估
├── examples/              # 杀手级 Demo + 策略示例
├── tests/                 # 300+ 测试用例
├── Dockerfile             # API Proxy Docker 镜像
├── docker-compose.yml     # 团队一键部署
└── pyproject.toml
```

## 协议分发

AgentGuard 设计为五种形态覆盖所有场景：

| 形态 | 适用场景 | 侵入性 |
|:---|:---|:---|
| **Python SDK** | openclaw/hermes 等 Python Agent 框架 | 2 行代码 |
| **CLI** | CI/CD 流水线、脚本集成 | 零侵入 |
| **MCP Server** | Cursor/Copilot/Claude Code 等 AI IDE | IDE 插件 |
| **API Proxy** | 任意 LLM API 调用（零代码改动） | 改环境变量 |
| **LSP Server** | VS Code 等编辑器原生诊断 | IDE 插件 |

### API Proxy 一键部署

```bash
# Docker 部署
docker run -d -p 8080:8080 \
  -v $(pwd)/policy.yaml:/policies/policy.yaml \
  -e AGENTGUARD_POLICY=/policies/policy.yaml \
  agentguard/proxy:latest

# 客户端配置（零代码）
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
# 之后所有 AI 工具的 LLM 请求自动经过 AgentGuard 校验
```

## 路线图

| 阶段 | 内容 | 状态 |
|:---|:---|:---|
| Phase 1 | Python SDK + CLI + 测试 | ✅ 完成 |
| Phase 2 | MCP Server（IDE 生态接入） | ✅ 完成 |
| Phase 2.5 | Schema Guard 增强（类型修复/枚举匹配/嵌套校验） | ✅ 完成 |
| Phase 3 | API Proxy（零侵入安全层） | ✅ 完成 |
| Phase 3b | LSP Server（编辑器原生诊断） | 📋 规划中 |
| Phase 4 | Dashboard + PyPI 发布 | 📋 进行中 |

## 支持我们

如果你觉得 AgentGuard 有用，请给我们一个 ⭐！

[![GitHub Stars](https://img.shields.io/github/stars/Churman1113/AgentGuard?style=social)](https://github.com/Churman1113/AgentGuard)

## License

MIT
