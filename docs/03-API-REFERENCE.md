# AI Output Guard — 公开 API 参考 v1.0

> 本文档定义 AI Output Guard 的完整公开接口。所有内部实现细节不在本文档范围内。
> 版本约定：遵循 SemVer，主版本号内保证向后兼容。

---

## 一、快速导入

```python
from agentguard import Guard, GuardResult, GuardLevel, CheckResult
from agentguard import guarded, GuardContext          # 装饰器 & 上下文管理器
from agentguard import AsyncGuard                     # 异步版本
from agentguard.errors import (                       # 异常类
    GuardError,
    GuardTimeoutError,
    SchemaValidationError,
    PolicyLoadError,
    EmbeddingModelError,
)
```

---

## 二、核心类：Guard

### 2.1 构造函数

```python
Guard(
    # ── Schema Guard ──
    schema: Optional[Union[type[BaseModel], dict]] = None,
    # Pydantic Model 类 或 JSON Schema dict。传 None 则跳过结构校验。

    # ── Semantic Guard ──
    semantic: bool = False,
    # 是否启用语义校验。默认 False。

    semantic_mode: Literal["auto", "rule", "classifier", "embedding"] = "auto",
    # 语义校验模式：
    #   "auto"       — 自动选择（规则→分类器→Embedding，逐层升级）
    #   "rule"       — 仅规则匹配（零延迟，零误报）
    #   "classifier" — 规则 + 轻量分类器
    #   "embedding"  — 规则 + 分类器 + Embedding（需安装 agentguard[semantic]）

    dangerous_intents: Optional[list[str]] = None,
    # 自定义危险意图列表。与内置意图合并。
    # 可用内置意图名：drop_table, delete_all, execute_shell, ssh_connect,
    #   send_email, access_secret, modify_system, network_request,
    #   data_exfiltration, pii_exposure

    similarity_threshold: float = 0.85,
    # Embedding 相似度阈值（0.0-1.0）。越高越严格。

    # ── Policy Guard ──
    policy: Optional[Union[str, dict]] = None,
    # 策略配置。可以是：
    #   str — YAML 文件路径（.yaml/.yml）或 YAML 字符串
    #   dict — 已解析的策略字典

    # ── 全局行为 ──
    on_fail: Literal["deny", "pass", "warn"] = "deny",
    # 校验失败时的行为：
    #   "deny" — 拦截，GuardResult.level = DENY
    #   "pass" — 放行但记录，level = PASS
    #   "warn" — 放行并警告，level = WARN

    on_error: Literal["pass", "deny"] = "pass",
    # Guard 自身出错时的降级行为（Fail-Open / Fail-Closed）。

    auto_fix: bool = True,
    # 是否尝试自动修正。仅影响 Schema Guard。

    audit: bool = True,
    # 是否记录审计日志。

    strict_schema: bool = False,
    # Schema 严格模式：多余字段视为错误。

    timeout: Optional[dict[str, int]] = None,
    # 各层超时（毫秒）。默认 {"schema": 100, "semantic": 500, "policy": 200}。

    name: Optional[str] = None,
    # Guard 实例名称，用于审计日志区分多个 Guard 实例。
)
```

### 2.2 validate 方法

```python
guard.validate(
    output: str,
    context: Optional[dict] = None,
) -> GuardResult
```

**参数**：

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `output` | `str` | LLM 的原始输出文本。通常是 JSON 字符串或自由文本。 |
| `context` | `dict \| None` | 可选的上下文信息，传递给 Policy Guard 用于条件匹配。例如 `{"agent": "openclaw", "env": "production"}` |

**返回**：`GuardResult`（见第三节）

**异常**：此方法**不抛出异常**——所有错误均降级处理并反映在 GuardResult 中。

### 2.3 validate_batch 方法

```python
guard.validate_batch(
    outputs: list[str],
    context: Optional[dict] = None,
) -> list[GuardResult]
```

批量校验，共享 Embedding 计算以提升吞吐。返回与 `outputs` 等长的 `GuardResult` 列表。

### 2.4 其他方法

```python
guard.update_policy(policy: Union[str, dict]) -> None
# 运行时热更新策略。支持 YAML 字符串或文件路径。

guard.add_intent(name: str, patterns: Optional[list[str]] = None) -> None
# 运行时添加自定义危险意图。patterns 为正则表达式列表。

guard.get_status() -> dict
# 返回当前 Guard 配置快照。
# 示例返回：{"name": "my-guard", "schema": "AgentAction", "semantic_mode": "rule",
#           "policy_rules": 5, "intents": ["drop_table", ...]}

guard.get_audit_log(limit: int = 100, level: Optional[GuardLevel] = None) -> list[dict]
# 查询审计日志。level 参数可过滤特定级别。
```

---

## 三、数据结构

### 3.1 GuardResult

```python
@dataclass
class GuardResult:
    raw: str                       # 原始 LLM 输出（不变）
    output: Optional[str]          # 最终输出（可能被修正后替换，或 DENY 时为 None）
    level: GuardLevel              # 最终判定
    checks: list[CheckResult]      # 各层校验结果（按执行顺序）
    blocked_by: Optional[str]      # 被哪一层拦截（"schema" / "semantic" / "policy"）
    audit_id: Optional[str]        # 审计日志 ID（格式 "ag-xxxxxxxxxxxx"）
    timestamp: float               # 校验时间戳

    # ── 便利属性 ──
    @property
    def is_safe(self) -> bool:
        """输出是否安全可用。PASS / FIX / WARN 均为 True。"""
        return self.level in (GuardLevel.PASS, GuardLevel.FIX, GuardLevel.WARN)

    @property
    def needs_human(self) -> bool:
        """是否需要人工确认。"""
        return self.level == GuardLevel.ASK_HUMAN

    @property
    def was_fixed(self) -> bool:
        """是否经过自动修正。"""
        return self.level == GuardLevel.FIX

    @property
    def first_error(self) -> Optional[CheckResult]:
        """第一个失败的校验结果。"""
        return next((c for c in self.checks if not c.passed), None)

    @property
    def total_duration_ms(self) -> float:
        """总校验耗时（毫秒）。"""
        return sum(c.duration_ms for c in self.checks)

    def to_dict(self) -> dict:
        """序列化为字典。"""

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串。"""
```

### 3.2 CheckResult

```python
@dataclass
class CheckResult:
    layer: str              # 校验层："schema" / "semantic" / "policy" / "timeout" / "error"
    passed: bool            # 是否通过
    level: GuardLevel       # 判定级别
    message: str            # 人类可读说明（英文）
    details: dict           # 详细信息（结构因 layer 而异）
    fix: Optional[str]      # 修正后的内容（仅 Schema Fix 时非 None）
    confidence: float       # 置信度 0.0-1.0（1.0 = 确定性判断）
    duration_ms: float      # 本层校验耗时（毫秒）
```

**details 结构**（按 layer）：

Schema Guard details:
```json
{
  "errors": [
    {"field": "method", "type": "literal_error", "message": "..."}
  ],
  "fixes_applied": ["enum_fuzzy_match: DELTE → DELETE"]
}
```

Semantic Guard details:
```json
{
  "matched_intent": "drop_table",
  "match_type": "rule",           // rule / classifier / embedding / llm_judge
  "pattern": "\\bDROP\\s+TABLE\\b",  // rule 模式时
  "confidence": 1.0,
  "all_scores": {"drop_table": 1.0, "delete_all": 0.0, ...}  // classifier/embedding 模式时
}
```

Policy Guard details:
```json
{
  "rule": "禁止访问生产数据库",
  "action": "deny",
  "timeout": 300,                 // ask_human 时
  "fallback": "deny"              // ask_human 时
}
```

### 3.3 GuardLevel

```python
class GuardLevel(Enum):
    PASS = "pass"              # 通过，输出安全
    WARN = "warn"              # 通过但有警告（低置信度风险）
    FIX = "fix"                # 自动修正后通过
    ASK_HUMAN = "ask_human"   # 需人工确认
    DENY = "deny"              # 拦截，输出不安全
```

**严重度排序**：`PASS < WARN < FIX < ASK_HUMAN < DENY`

---

## 四、装饰器模式

### 4.1 @guarded

```python
from agentguard import guarded

@guarded(
    schema=AgentAction,
    semantic=True,
    semantic_mode="rule",
    policy="policies/agent.yaml",
)
async def call_llm(prompt: str) -> str:
    """LLM 调用函数 — 返回值自动经过 Guard 校验"""
    return await llm.generate(prompt)

# 调用：
result = await call_llm("Delete all users")
# result 是 GuardResult，不是 str
# 如果需要直接获取安全输出：
safe_output = result.output  # None if DENY
```

**工作机制**：装饰器拦截函数返回值，自动调用 `guard.validate(return_value)`，将 GuardResult 作为最终返回值。

### 4.2 GuardContext

```python
from agentguard import GuardContext, GuardLevel

with GuardContext(
    schema=APIResponse,
    semantic=True,
    on_fail="deny",
) as guard:
    raw = llm.generate(prompt)
    result = guard.validate(raw)
    if result.is_safe:
        process(result.output)
    else:
        handle_block(result)
```

**用途**：临时创建一个 Guard 上下文，自动管理审计日志的会话标记。

---

## 五、AsyncGuard

```python
from agentguard import AsyncGuard, GuardLevel

guard = AsyncGuard(
    schema=AgentAction,
    semantic=True,
    semantic_mode="embedding",   # Embedding 计算使用 asyncio
    policy="policies/agent.yaml",
)

# 异步校验 — Embedding 和 LLM-as-Judge 使用 aiohttp
result = await guard.validate(raw_output, context={"agent": "openclaw"})

# 异步批量校验
results = await guard.validate_batch(outputs)

# 异步热更新
await guard.update_policy("policies/new-policy.yaml")
```

**与 Guard 的差异**：
- 构造参数完全相同
- `validate` / `validate_batch` / `update_policy` 均为 `async` 方法
- Embedding 计算、LLM-as-Judge 调用使用 `aiohttp` 异步执行
- 规则模式和分类器模式仍然是同步执行（延迟极低，无需异步）

---

## 六、插件系统

### 6.1 自定义 Guard 层

```python
from agentguard.registry import BaseGuard, GuardRegistry, CheckResult, GuardLevel

class RateLimitGuard(BaseGuard):
    """自定义 Guard：检查 LLM 输出中的速率限制信息"""

    name = "rate_limit"

    def __init__(self, max_calls: int = 100):
        self.max_calls = max_calls
        self.call_count = 0

    def check(self, output: str) -> CheckResult:
        self.call_count += 1
        if self.call_count > self.max_calls:
            return CheckResult(
                layer="rate_limit",
                passed=False,
                level=GuardLevel.DENY,
                message=f"调用次数超限: {self.call_count}/{self.max_calls}",
                confidence=1.0,
            )
        return CheckResult(
            layer="rate_limit",
            passed=True,
            level=GuardLevel.PASS,
            message="调用次数正常",
            confidence=1.0,
        )

# 注册到 Guard
guard = Guard(schema=AgentAction)
guard.add_guard(RateLimitGuard(max_calls=50))
```

### 6.2 自定义策略动作

```python
from agentguard.policy.actions import ActionHandler, ActionContext, ActionResult

class WebhookNotifyAction(ActionHandler):
    """自定义策略动作：触发 Webhook 通知"""

    action_type = "webhook_notify"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def execute(self, context: ActionContext) -> ActionResult:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            await session.post(self.webhook_url, json={
                "event": "agentguard_block",
                "rule": context.rule_name,
                "output": context.output[:200],  # 截断
                "level": context.level.value,
            })
        return ActionResult(action="notify", message="Webhook sent")
```

在策略文件中使用：
```yaml
rules:
  - name: "高危操作通知"
    condition:
      field: "output.method"
      operator: "equals"
      value: "DELETE"
    action: webhook_notify
    webhook_url: "https://hooks.slack.com/services/xxx"
```

### 6.3 pip 安装的插件

```python
# 第三方插件通过 entry_points 注册
# 在 pyproject.toml 中：
[project.entry-points."agentguard.guards"]
rate_limit = "agentguard_ratelimit:RateLimitGuard"

[project.entry-points."agentguard.actions"]
webhook = "agentguard_webhook:WebhookNotifyAction"

# 安装后自动可用
# pip install agentguard-plugin-ratelimit
# pip install agentguard-plugin-webhook
```

---

## 七、异常类

```python
class GuardError(Exception):
    """Guard 基础异常"""
    layer: str          # 出错的层
    message: str        # 错误信息

class GuardTimeoutError(GuardError):
    """校验超时"""
    layer: str          # 超时的层

class SchemaValidationError(GuardError):
    """Schema 校验错误（构造时 schema 无效）"""

class PolicyLoadError(GuardError):
    """策略文件加载/解析错误"""

class EmbeddingModelError(GuardError):
    """Embedding 模型加载/推理错误"""
```

**重要**：`Guard.validate()` 方法**不会抛出**这些异常——所有异常都在内部捕获并降级处理。这些异常类仅在以下场景抛出：
- 构造 Guard 时参数无效
- 显式调用 `update_policy()` 时文件格式错误
- 直接使用底层组件（如 `SchemaGuard` / `SemanticGuard`）

---

## 八、配置参考

### 8.1 环境变量

| 变量 | 类型 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `AGENTGUARD_POLICY` | str | — | 策略文件路径 |
| `AGENTGUARD_SEMANTIC_MODE` | str | `"auto"` | 语义校验模式 |
| `AGENTGUARD_ON_FAIL` | str | `"deny"` | 失败行为 |
| `AGENTGUARD_ON_ERROR` | str | `"pass"` | 错误降级行为 |
| `AGENTGUARD_AUTO_FIX` | bool | `"true"` | 自动修正 |
| `AGENTGUARD_AUDIT` | bool | `"true"` | 审计日志 |
| `AGENTGUARD_AUDIT_STORE` | str | `"memory"` | 审计存储后端 |
| `AGENTGUARD_AUDIT_PATH` | str | — | 审计存储路径 |
| `AGENTGUARD_LOG_LEVEL` | str | `"WARNING"` | 日志级别 |

### 8.2 配置文件 (.agentguard.yaml)

完整配置参考：

```yaml
guard:
  on_fail: deny
  on_error: pass
  auto_fix: true
  audit: true
  strict_schema: false

  semantic:
    mode: rule
    threshold: 0.85
    dangerous_intents:
      - drop_table
      - execute_shell
      - access_secret
    custom_intents:              # 自定义意图（含正则规则）
      custom_api_call:
        patterns:
          - "\\bapi\\.internal\\.company\\.com\\b"
          - "\\binternal[_-]?endpoint\\b"
        level: deny

  policy:
    path: ./policy.yaml
    watch: true
    reload_interval: 30

  audit:
    store: sqlite                # memory / file / sqlite / remote
    path: ./audit.db
    hash_chain: true
    retention_days: 90
    sanitize: true               # 脱敏 PII
    sanitize_fields:             # 自定义脱敏字段
      - "password"
      - "api_key"
      - "token"

  timeout:
    schema: 100
    semantic: 500
    policy: 200

  plugins:                       # 启用的插件
    - agentguard-plugin-ratelimit
    - agentguard-plugin-webhook
```

---

## 九、CLI 参考

### 9.1 命令总览

```
agentguard [OPTIONS] COMMAND [ARGS]

Commands:
  check       校验 AI 输出
  config      配置管理
  audit       审计日志查询
  daemon      启动守护进程
  version     显示版本信息
```

### 9.2 check 子命令

```bash
agentguard check [OPTIONS] [INPUT]

# INPUT 可以是：
#   - 命令行参数字符串
#   - 文件路径（自动检测）
#   - stdin（--stdin 模式）

Options:
  --policy PATH          策略文件路径
  --schema PATH          JSON Schema 文件路径
  --semantic MODE        语义模式: auto/rule/classifier/embedding
  --layers LAYERS        启用的层: schema,semantic,policy (逗号分隔)
  --on-fail ACTION       失败行为: deny/pass/warn
  --auto-fix / --no-auto-fix  自动修正 (默认开启)
  --format FORMAT        输出格式: json/yaml/table/human (默认 human)
  --stdin                从 stdin 读取输入
  --context JSON         上下文信息 (JSON 字符串)
  --verbose / -v         显示详细信息
```

**输出格式示例**：

```bash
# human 格式（默认）
$ agentguard check --policy ./policy.yaml '{"method": "DELETE", "endpoint": "/prod/db"}'
✗ DENIED by policy guard
  Rule: 禁止访问生产数据库
  Action: deny
  Message: 策略禁止访问生产环境
  Duration: 2.3ms

# json 格式
$ agentguard check --format json '{"method": "DELETE", "endpoint": "/prod/db"}'
{
  "level": "deny",
  "blocked_by": "policy",
  "output": null,
  "checks": [...],
  "audit_id": "ag-a1b2c3d4e5f6",
  "total_duration_ms": 2.3
}

# table 格式
$ agentguard check --format table '{"endpoint": "/api/users", "method": "DELTE"}'
┌───────────┬────────┬──────────┬──────────────────────────────┐
│ Layer     │ Result │ Duration │ Message                      │
├───────────┼────────┼──────────┼──────────────────────────────┤
│ schema    │ FIX    │ 0.8ms    │ 自动修正: DELTE → DELETE      │
│ semantic  │ PASS   │ 0.1ms    │ 语义校验通过                  │
│ policy    │ PASS   │ 0.3ms    │ 无策略命中，默认放行           │
├───────────┼────────┼──────────┼──────────────────────────────┤
│ TOTAL     │ FIX    │ 1.2ms    │ 自动修正后通过                │
└───────────┴────────┴──────────┴──────────────────────────────┘
```

### 9.3 退出码

| 退出码 | 含义 |
|:---|:---|
| 0 | 校验通过（PASS / FIX / WARN） |
| 1 | 校验拦截（DENY） |
| 2 | 需人工确认（ASK_HUMAN） |
| 3 | Guard 内部错误 |
| 4 | 参数错误 |

---

## 十、版本兼容性

### 10.1 Python 版本

| Python 版本 | 支持状态 |
|:---|:---|
| 3.10 | ✅ 最低支持 |
| 3.11 | ✅ |
| 3.12 | ✅ |
| 3.13 | ✅ |
| 3.9 及以下 | ❌ |

### 10.2 可选依赖组

```bash
pip install ai-output-guard                    # 核心引擎（Schema + Semantic 规则模式 + Policy）
pip install ai-output-guard[semantic]          # + Embedding 模型（sentence-transformers）
pip install ai-output-guard[classifier]        # + 轻量分类器（fasttext-wheel）
pip install ai-output-guard[all]               # + 所有可选依赖
pip install ai-output-guard[dev]               # + 开发/测试工具
```

### 10.3 框架集成包（计划中）

```bash
pip install agentguard-langchain          # LangChain 集成
pip install agentguard-autogen            # AutoGen 集成
pip install agentguard-crewai             # CrewAI 集成
```

---

## 十一、从竞品迁移

### 11.1 从 instructor 迁移

```python
# instructor 写法
import instructor
client = instructor.from_openai(openai_client)
result = client.chat.completions.create(
    response_model=AgentAction,
    messages=[...],
)

# AI Output Guard 等价写法（保留 instructor 的提取能力 + 增加安全层）
from agentguard import Guard
raw = await llm.generate(prompt)
result = Guard(schema=AgentAction, semantic=True, policy="policies/agent.yaml").validate(raw)
if result.is_safe:
    action = AgentAction.model_validate_json(result.output)
```

### 11.2 从 guardrails-ai 迁移

```python
# guardrails-ai 写法
from guardrails import Guard as GRGuard
gr = GRGuard.from_rail("spec.rail")
result = gr(openai_client, prompt="...")

# AI Output Guard 等价写法（更简洁的三层递进）
from agentguard import Guard
guard = Guard(schema=AgentAction, semantic=True, policy="policies/agent.yaml")
raw = await llm.generate(prompt)
result = guard.validate(raw)
```

### 11.3 从 NeMo Guardrails 迁移

```python
# NeMo 写法（Colang DSL）
define flow
  user ask about database
  bot refuse database access

# AI Output Guard 等价写法（YAML 声明式策略）
# policies/agent.yaml
rules:
  - name: "禁止数据库访问"
    condition:
      field: "output.action"
      operator: "in"
      value: ["query_db", "modify_db", "drop_table"]
    action: deny
    message: "策略禁止数据库访问"
```
