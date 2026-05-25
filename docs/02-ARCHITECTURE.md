# AI Output Guard — 架构设计文档 v2.0

> **v2.0 变更**：修复核心 bug、升级 Semantic Guard 方案、规范 Policy DSL、补充错误处理/安全/部署/测试/性能设计

---

## 一、系统全景架构

```
                          ┌─────────────────────────────────────┐
                          │          用户 / AI 工具              │
                          │  (Cursor, Copilot, Agent, 终端...)   │
                          └──────────────┬──────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
              ┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
              │ MCP Server │      │ LSP Server  │     │  API Proxy  │
              │ (AI 工具)  │      │ (IDE 插件)   │     │ (零侵入)    │
              └─────┬─────┘      └──────┬──────┘     └──────┬──────┘
                    │                    │                    │
                    └────────────────────┼────────────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │    Protocol Bridge   │
                              │  (协议适配层)         │
                              └──────────┬──────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
              ┌─────▼─────┐      ┌──────▼──────┐     ┌──────▼──────┐
              │   Schema   │      │  Semantic   │     │   Policy    │
              │   Guard    │─────▶│   Guard     │────▶│   Guard     │
              │ (结构校验)  │      │ (语义校验)   │     │ (策略控制)   │
              └───────────┘      └─────────────┘     └──────┬──────┘
                                                               │
                                                         ┌─────▼─────┐
                                                         │  Audit &  │
                                                         │  Logger   │
                                                         │ (审计日志) │
                                                         └───────────┘
```

**设计原则**：

1. **渐进式流水线**：三层递进执行，前一层失败时根据 auto_fix 决定是否继续
2. **Fail-Open**：Guard 自身出错不阻断业务（可配置为 Fail-Closed）
3. **可降级**：每层有独立降级策略，高级模式不可用时自动降级到基础模式
4. **零信任输入**：所有输入视为不可信，Guard 内部不做任何假设

---

## 二、模块划分

### 2.1 核心引擎层（agentguard-core）

```
agentguard/
├── __init__.py              # 导出 Guard, GuardResult, GuardLevel
├── guard.py                 # Guard 主入口 — 编排三层校验
├── schema_guard.py          # Schema Guard — 结构校验
├── semantic_guard.py        # Semantic Guard — 语义校验
├── policy_guard.py          # Policy Guard — 策略控制
├── result.py                # GuardResult — 校验结果数据结构
├── registry.py              # GuardRegistry — 自定义校验器注册
├── config.py                # 配置加载与管理
├── errors.py                # 统一异常定义
├── audit/
│   ├── __init__.py
│   ├── logger.py            # 审计日志记录
│   ├── store.py             # 日志存储（内存/文件/远程）
│   └── hash_chain.py        # 哈希链防篡改
├── semantic/
│   ├── __init__.py
│   ├── rule_matcher.py      # 规则模式 — 关键词/正则/启发式
│   ├── classifier.py        # 分类器模式 — FastText/小模型
│   ├── embedding.py         # Embedding 模式 — sentence-transformers
│   ├── llm_judge.py         # LLM-as-Judge 模式（可选）
│   └── intent_registry.py   # 意图注册与管理
├── policy/
│   ├── __init__.py
│   ├── parser.py            # 策略 DSL 解析器
│   ├── engine.py            # 规则匹配引擎
│   ├── operators.py         # 运算符实现
│   ├── actions.py           # 动作执行器（allow/deny/modify/ask_human）
│   └── validator.py         # 策略文件校验
├── fix/
│   ├── __init__.py
│   ├── schema_fixer.py      # Schema 自动修正
│   ├── enum_fixer.py        # 枚举值模糊匹配修正
│   ├── type_fixer.py        # 类型转换修正
│   └── retry.py             # LLM 重试修正（可选，调用 LLM 重新生成）
└── plugins/
    ├── __init__.py
    └── loader.py            # 插件加载器（entry_points）
```

### 2.2 协议适配层（agentguard-protocol）

```
agentguard-protocol/
├── mcp_server/              # MCP Server 实现
│   ├── __init__.py
│   ├── server.py            # MCP 协议处理
│   ├── tools.py             # MCP Tool 定义
│   └── resources.py         # MCP Resource 定义（策略文件/审计日志）
├── lsp_server/              # LSP Server 实现
│   ├── __init__.py
│   ├── server.ts            # LSP 协议主入口（TypeScript）
│   ├── diagnostics.ts       # 诊断信息生成
│   ├── code_actions.ts      # Code Action — 快速修正
│   └── document_sync.ts     # 文档同步与变更检测
├── cli/                     # CLI 实现
│   ├── __init__.py
│   ├── main.py              # Click/Typer CLI 入口
│   ├── config_cmd.py        # 配置管理子命令
│   └── daemon.py            # 守护进程模式
└── proxy/                   # API Proxy 实现
    ├── __init__.py
    ├── server.py            # HTTP 代理服务器
    ├── interceptor.py       # 请求拦截器
    ├── transformer.py       # 请求/响应转换
    ├── router.py            # LLM API 路由识别
    └── health.py            # 健康检查端点
```

### 2.3 Dashboard（agentguard-dashboard）— Phase 4

```
agentguard-dashboard/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── api/                 # REST API
│   │   ├── audit.py         # 审计日志查询
│   │   ├── policies.py      # 策略管理 CRUD
│   │   ├── stats.py         # 统计数据
│   │   └── auth.py          # 认证
│   ├── models.py            # 数据模型
│   └── ws.py                # WebSocket 实时推送
└── frontend/
    ├── src/
    │   ├── App.vue
    │   ├── views/
    │   │   ├── Dashboard.vue    # 概览：拦截率/趋势/热点
    │   │   ├── Policies.vue     # 策略管理
    │   │   ├── AuditLog.vue     # 审计日志
    │   │   ├── Intents.vue      # 意图库管理
    │   │   └── Settings.vue     # 设置
    │   └── components/
    └── package.json
```

---

## 三、核心引擎详细设计

### 3.1 Guard 主入口

```python
from pydantic import BaseModel
from typing import Optional, Union
from agentguard.result import GuardResult, GuardLevel
from agentguard.errors import GuardError, GuardTimeoutError

class Guard:
    """AI Output Guard 主入口 — 编排三层校验"""

    def __init__(
        self,
        schema: Optional[Union[type[BaseModel], dict]] = None,  # Schema Guard
        semantic: bool = False,                                   # 启用语义守卫
        semantic_mode: str = "auto",      # auto/rule/classifier/embedding
        dangerous_intents: Optional[list[str]] = None,           # 危险意图列表
        similarity_threshold: float = 0.85,                      # 语义相似度阈值
        policy: Optional[Union[str, dict]] = None,               # Policy Guard
        on_fail: str = "deny",            # deny | pass | warn
        on_error: str = "pass",           # Guard 自身出错时的降级策略
        auto_fix: bool = True,            # 自动修正尝试
        audit: bool = True,               # 记录审计日志
        timeout: Optional[dict] = None,   # 各层超时配置
    ):
        self.schema_guard = SchemaGuard(schema) if schema else None
        self.semantic_guard = SemanticGuard(
            mode=semantic_mode,
            dangerous_intents=dangerous_intents or [],
            threshold=similarity_threshold,
        ) if semantic else None
        self.policy_guard = PolicyGuard(policy) if policy else None
        self.on_fail = on_fail
        self.on_error = on_error
        self.auto_fix = auto_fix
        self.audit = audit

        # 超时配置（毫秒）
        self.timeout = timeout or {
            "schema": 100,
            "semantic": 500,
            "policy": 200,
        }

    def validate(self, output: str, context: Optional[dict] = None) -> GuardResult:
        """三层递进校验"""
        result = GuardResult(raw=output)
        current_output = output  # 追踪当前输出（可能被修正）

        try:
            # Layer 1: Schema Guard
            if self.schema_guard:
                sr = self._check_with_timeout(
                    self.schema_guard.check,
                    current_output,
                    self.timeout["schema"]
                )
                result.add_check("schema", sr)
                if not sr.passed:
                    if self.auto_fix and sr.fix:
                        current_output = sr.fix  # 使用修正后的输出
                        result.output = current_output
                    else:
                        return result.finalize(on_fail=self.on_fail)

            # Layer 2: Semantic Guard
            if self.semantic_guard:
                sr = self._check_with_timeout(
                    self.semantic_guard.check,
                    current_output,
                    self.timeout["semantic"]
                )
                result.add_check("semantic", sr)
                if not sr.passed:
                    return result.finalize(on_fail=self.on_fail)

            # Layer 3: Policy Guard
            if self.policy_guard:
                sr = self._check_with_timeout(
                    self.policy_guard.check,
                    current_output,
                    context or {},
                    self.timeout["policy"]
                )
                result.add_check("policy", sr)
                if not sr.passed:
                    return result.finalize(on_fail=self.on_fail)

        except GuardTimeoutError as e:
            # 超时降级
            result.add_check("timeout", CheckResult(
                layer="timeout",
                passed=True,  # Fail-Open
                level=GuardLevel.WARN,
                message=f"校验超时: {e.layer}，已降级放行",
                details={"timeout_layer": e.layer},
            ))
        except GuardError as e:
            # Guard 自身错误降级
            result.add_check("error", CheckResult(
                layer="error",
                passed=self.on_error == "pass",
                level=GuardLevel.WARN if self.on_error == "pass" else GuardLevel.DENY,
                message=f"Guard 内部错误: {e}",
                details={"error": str(e)},
            ))

        return result.finalize(on_fail=self.on_fail)

    def _check_with_timeout(self, fn, *args, timeout_ms: int = 500):
        """带超时的校验调用"""
        import signal
        import time

        def handler(signum, frame):
            raise GuardTimeoutError(layer=getattr(fn, '__self__', None).__class__.__name__)

        # 注意：signal 方案仅 Unix 可用
        # 生产环境用 asyncio.wait_for 或 threading + Event
        old = signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, timeout_ms / 1000)
        try:
            return fn(*args)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
```

### 3.2 GuardResult 数据结构

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
import uuid
import time

class GuardLevel(Enum):
    PASS = "pass"
    WARN = "warn"        # 通过但有警告
    FIX = "fix"          # 自动修正后通过
    ASK_HUMAN = "ask_human"  # 需人工确认
    DENY = "deny"        # 拦截

@dataclass
class CheckResult:
    layer: str              # "schema" | "semantic" | "policy" | "timeout" | "error"
    passed: bool
    level: GuardLevel
    message: str            # 人类可读的说明
    details: dict = field(default_factory=dict)
    fix: Optional[str] = None      # 修正后的内容
    confidence: float = 1.0        # 置信度 (0.0-1.0)
    duration_ms: float = 0.0       # 校验耗时

@dataclass
class GuardResult:
    raw: str                                 # 原始 LLM 输出
    output: Optional[str] = None             # 最终输出（可能被修正）
    level: GuardLevel = GuardLevel.PASS
    checks: list[CheckResult] = field(default_factory=list)
    blocked_by: Optional[str] = None         # 被哪一层拦截
    audit_id: Optional[str] = None           # 审计日志 ID
    timestamp: float = field(default_factory=time.time)

    def add_check(self, layer: str, check: CheckResult):
        self.checks.append(check)

    def finalize(self, on_fail: str = "deny") -> "GuardResult":
        """根据校验结果确定最终状态"""
        # 生成审计 ID
        self.audit_id = f"ag-{uuid.uuid4().hex[:12]}"

        failed = [c for c in self.checks if not c.passed]
        if not failed:
            self.level = GuardLevel.PASS
            if self.output is None:
                self.output = self.raw
        else:
            # 确定最严重的失败层
            worst = failed[-1]

            if worst.level == GuardLevel.ASK_HUMAN:
                self.level = GuardLevel.ASK_HUMAN
                self.blocked_by = worst.layer
                self.output = self.raw  # 保留原始输出供人工审核
            elif on_fail == "deny":
                self.level = GuardLevel.DENY
                self.blocked_by = worst.layer
                self.output = None
            elif on_fail == "warn":
                self.level = GuardLevel.WARN
                self.blocked_by = worst.layer
                self.output = self.raw
            elif on_fail == "pass":
                self.level = GuardLevel.PASS
                self.output = self.raw

        # 检查是否有 FIX 级别的修正
        fix_checks = [c for c in self.checks if c.level == GuardLevel.FIX and c.fix]
        if fix_checks and self.level == GuardLevel.PASS:
            self.level = GuardLevel.FIX
            # output 已在 Guard.validate() 中被更新为修正后的内容

        return self

    @property
    def is_safe(self) -> bool:
        """输出是否安全可用"""
        return self.level in (GuardLevel.PASS, GuardLevel.FIX, GuardLevel.WARN)

    @property
    def needs_human(self) -> bool:
        """是否需要人工确认"""
        return self.level == GuardLevel.ASK_HUMAN
```

### 3.3 Schema Guard 实现

```python
import json
import re
from typing import Optional, Union
from pydantic import BaseModel, ValidationError
from agentguard.result import CheckResult, GuardLevel
from agentguard.fix.enum_fixer import EnumFixer
from agentguard.fix.type_fixer import TypeFixer

class SchemaGuard:
    """结构守卫 — 校验 LLM 输出是否符合预期数据结构"""

    def __init__(self, schema: Union[type[BaseModel], dict], strict: bool = False):
        self.strict = strict  # 严格模式：多余字段报错

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            self.pydantic_model = schema
            self.json_schema = schema.model_json_schema()
        elif isinstance(schema, dict):
            self.json_schema = schema
            self.pydantic_model = None
        else:
            raise ValueError("schema 必须是 Pydantic Model 或 JSON Schema dict")

        # 初始化修正器
        self.enum_fixer = EnumFixer(self.json_schema)
        self.type_fixer = TypeFixer(self.json_schema)

    def check(self, output: str) -> CheckResult:
        """校验输出"""
        import time
        start = time.monotonic()

        # Step 1: 解析 JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            # 尝试修复常见 JSON 错误
            fixed_json = self._try_fix_json(output)
            if fixed_json is not None:
                data = fixed_json
            else:
                return CheckResult(
                    layer="schema",
                    passed=False,
                    level=GuardLevel.DENY,
                    message=f"JSON 解析失败: {e}",
                    details={"error": str(e), "position": f"line {e.lineno}, col {e.colno}"},
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Step 2: Pydantic 校验
        if self.pydantic_model:
            try:
                validated = self.pydantic_model.model_validate(data)
                return CheckResult(
                    layer="schema",
                    passed=True,
                    level=GuardLevel.PASS,
                    message="结构校验通过",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            except ValidationError as e:
                fix = self._try_fix(data, e)
                confidence = self._compute_fix_confidence(data, e)
                return CheckResult(
                    layer="schema",
                    passed=False,
                    level=GuardLevel.FIX if fix else GuardLevel.DENY,
                    message=f"结构校验失败: {e.error_count()} 个错误",
                    details={"errors": self._format_errors(e)},
                    fix=fix,
                    confidence=confidence,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Step 3: JSON Schema 校验（无 Pydantic 时）
        try:
            import jsonschema
            jsonschema.validate(data, self.json_schema)
            return CheckResult(
                layer="schema",
                passed=True,
                level=GuardLevel.PASS,
                message="结构校验通过",
                duration_ms=(time.monotonic() - start) * 1000,
            )
        except jsonschema.ValidationError as e:
            return CheckResult(
                layer="schema",
                passed=False,
                level=GuardLevel.DENY,
                message=f"JSON Schema 校验失败: {e.message}",
                details={"path": list(e.absolute_path), "error": e.message},
                duration_ms=(time.monotonic() - start) * 1000,
            )

    def _try_fix(self, data: dict, error: ValidationError) -> Optional[str]:
        """尝试自动修正"""
        fixed_data = dict(data)  # 浅拷贝
        any_fixed = False

        for err in error.errors():
            # 策略 1：枚举值模糊匹配
            if err["type"] == "literal_error" or err["type"] == "enum":
                fixed = self.enum_fixer.try_fix(fixed_data, err)
                if fixed:
                    any_fixed = True
                    continue

            # 策略 2：类型转换
            if err["type"].startswith("model_") or err["type"] in ("int_type", "float_type", "bool_type"):
                fixed = self.type_fixer.try_fix(fixed_data, err)
                if fixed:
                    any_fixed = True
                    continue

            # 策略 3：缺失字段 → 填充默认值
            if err["type"] == "missing":
                default = self._get_default(err["loc"])
                if default is not None:
                    self._set_nested(fixed_data, err["loc"], default)
                    any_fixed = True
                    continue

            # 策略 4：多余字段 → 剥离（非严格模式下）
            if err["type"] == "extra_forbidden" and not self.strict:
                self._del_nested(fixed_data, err["loc"])
                any_fixed = True
                continue

        if any_fixed:
            # 修正后重新校验
            try:
                self.pydantic_model.model_validate(fixed_data)
                return json.dumps(fixed_data, ensure_ascii=False)
            except ValidationError:
                return None  # 修正后仍然无效，放弃

        return None

    def _try_fix_json(self, raw: str) -> Optional[dict]:
        """尝试修复常见 JSON 语法错误"""
        # 常见问题：尾部逗号、单引号、注释
        cleaned = raw.strip()
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)  # 移除尾部逗号
        cleaned = cleaned.replace("'", '"')                  # 单引号→双引号
        cleaned = re.sub(r'//.*?\n', '\n', cleaned)         # 移除单行注释

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _compute_fix_confidence(self, data: dict, error: ValidationError) -> float:
        """计算修正置信度"""
        total_fields = len(self.json_schema.get("properties", {}))
        if total_fields == 0:
            return 1.0
        error_count = error.error_count()
        # 错误越少，置信度越高
        confidence = max(0.0, 1.0 - (error_count / total_fields))
        return round(confidence, 2)

    @staticmethod
    def _get_default(loc: tuple) -> Any:
        """获取字段默认值（简化实现）"""
        return None  # Pydantic 模型的默认值需要从模型中提取

    @staticmethod
    def _set_nested(data: dict, loc: tuple, value: Any):
        """设置嵌套字段值"""
        for key in loc[:-1]:
            data = data.setdefault(key, {})
        data[loc[-1]] = value

    @staticmethod
    def _del_nested(data: dict, loc: tuple):
        """删除嵌套字段"""
        for key in loc[:-1]:
            if key not in data:
                return
            data = data[key]
        data.pop(loc[-1], None)

    @staticmethod
    def _format_errors(error: ValidationError) -> list[dict]:
        """格式化错误信息"""
        return [
            {
                "field": ".".join(str(x) for x in e["loc"]),
                "type": e["type"],
                "message": e["msg"],
            }
            for e in error.errors()
        ]
```

### 3.4 Semantic Guard 实现（v2.0：分层决策）

```python
import time
from typing import Optional
from agentguard.result import CheckResult, GuardLevel
from agentguard.semantic.rule_matcher import RuleMatcher
from agentguard.semantic.classifier import IntentClassifier
from agentguard.semantic.intent_registry import IntentRegistry

class SemanticGuard:
    """语义守卫 — 分层决策校验 LLM 输出的语义安全性"""

    def __init__(
        self,
        mode: str = "auto",                    # auto/rule/classifier/embedding
        dangerous_intents: Optional[list[str]] = None,
        threshold: float = 0.85,
        enable_embedding: bool = False,         # Embedding 模型需要额外安装
        enable_llm_judge: bool = False,         # LLM-as-Judge 需要额外配置
    ):
        self.mode = mode
        self.threshold = threshold

        # 意图注册中心
        self.intent_registry = IntentRegistry()
        for intent in (dangerous_intents or []):
            self.intent_registry.register(intent)

        # Layer 1: 规则匹配（零延迟，零误报）
        self.rule_matcher = RuleMatcher(self.intent_registry)

        # Layer 2: 轻量分类器（低延迟，高准确率）
        self.classifier = IntentClassifier(self.intent_registry)

        # Layer 3: Embedding（可选，中等延迟）
        self._embedder = None
        if enable_embedding or mode == "embedding":
            try:
                from agentguard.semantic.embedding import EmbeddingMatcher
                self._embedder = EmbeddingMatcher(self.intent_registry, threshold)
            except ImportError:
                pass  # 降级到分类器模式

        # Layer 4: LLM-as-Judge（可选，高延迟高准确率）
        self._llm_judge = None
        if enable_llm_judge:
            try:
                from agentguard.semantic.llm_judge import LLMJudge
                self._llm_judge = LLMJudge()
            except ImportError:
                pass

    def check(self, output: str) -> CheckResult:
        """语义校验 — 分层决策"""
        start = time.monotonic()

        # Layer 1: 规则匹配（确定性拦截）
        rule_result = self.rule_matcher.match(output)
        if rule_result.matched:
            return CheckResult(
                layer="semantic",
                passed=False,
                level=GuardLevel.DENY,
                message=f"语义匹配到危险意图: {rule_result.intent}（规则命中）",
                details={
                    "matched_intent": rule_result.intent,
                    "match_type": "rule",
                    "pattern": rule_result.pattern,
                    "confidence": 1.0,
                },
                confidence=1.0,
                duration_ms=(time.monotonic() - start) * 1000,
            )

        # Layer 2: 轻量分类器
        if self.mode in ("auto", "classifier"):
            cls_result = self.classifier.classify(output)
            if cls_result.confidence >= self.threshold:
                level = GuardLevel.DENY if cls_result.confidence >= 0.95 else GuardLevel.WARN
                return CheckResult(
                    layer="semantic",
                    passed=cls_result.confidence < self.threshold,
                    level=level,
                    message=f"语义匹配到危险意图: {cls_result.intent}（分类器，置信度 {cls_result.confidence:.2%}）",
                    details={
                        "matched_intent": cls_result.intent,
                        "match_type": "classifier",
                        "confidence": cls_result.confidence,
                    },
                    confidence=cls_result.confidence,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Layer 3: Embedding 相似度
        if self._embedder and self.mode in ("auto", "embedding"):
            emb_result = self._embedder.match(output)
            if emb_result.similarity >= self.threshold:
                return CheckResult(
                    layer="semantic",
                    passed=False,
                    level=GuardLevel.WARN,  # Embedding 模式只标记 WARN，不直接 DENY
                    message=f"语义近似危险意图: {emb_result.intent}（相似度 {emb_result.similarity:.2%}）",
                    details={
                        "matched_intent": emb_result.intent,
                        "match_type": "embedding",
                        "similarity": emb_result.similarity,
                    },
                    confidence=emb_result.similarity,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Layer 4: LLM-as-Judge（可选）
        if self._llm_judge:
            judge_result = self._llm_judge.judge(output)
            if not judge_result.safe:
                return CheckResult(
                    layer="semantic",
                    passed=False,
                    level=GuardLevel.ASK_HUMAN,  # LLM 判断不确定，交给人工
                    message=f"LLM 判定可能不安全: {judge_result.reason}",
                    details={
                        "match_type": "llm_judge",
                        "reason": judge_result.reason,
                    },
                    confidence=judge_result.confidence,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # 所有层都未拦截
        return CheckResult(
            layer="semantic",
            passed=True,
            level=GuardLevel.PASS,
            message="语义校验通过",
            details={"mode": self.mode},
            duration_ms=(time.monotonic() - start) * 1000,
        )
```

#### 3.4.1 规则匹配器（RuleMatcher）

```python
import re
from dataclasses import dataclass

@dataclass
class RuleMatchResult:
    matched: bool
    intent: str = ""
    pattern: str = ""

class RuleMatcher:
    """Layer 1: 规则匹配 — 确定性高危模式拦截"""

    # 内置高危规则（正则表达式）
    BUILTIN_RULES: dict[str, list[str]] = {
        "drop_table": [
            r"\bDROP\s+TABLE\b",
            r"\bTRUNCATE\s+TABLE\b",
        ],
        "delete_all": [
            r"\bDELETE\s+FROM\s+\w+\s*;?\s*$",   # DELETE FROM table; (无 WHERE)
            r"\brm\s+-rf\s+/",
            r"\brm\s+-r\s+/",
        ],
        "execute_shell": [
            r"\bsudo\s+",
            r"\bchmod\s+777\b",
            r"\bsu\s+root\b",
        ],
        "access_secret": [
            r"\b(api[_-]?key|secret|password|token|credential)\s*[:=]",
            r"\bAWS_SECRET_ACCESS_KEY\b",
        ],
        "data_exfiltration": [
            r"\bcurl\s+.*\|\s*sh\b",
            r"\bwget\s+.*\|\s*sh\b",
        ],
    }

    def __init__(self, intent_registry):
        self.rules = dict(self.BUILTIN_RULES)
        # 加载用户自定义规则
        for intent in intent_registry.get_all():
            if intent.rules:
                self.rules.setdefault(intent.name, []).extend(intent.rules)

    def match(self, output: str) -> RuleMatchResult:
        for intent_name, patterns in self.rules.items():
            for pattern in patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    return RuleMatchResult(
                        matched=True,
                        intent=intent_name,
                        pattern=pattern,
                    )
        return RuleMatchResult(matched=False)
```

#### 3.4.2 轻量分类器（IntentClassifier）

```python
from dataclasses import dataclass

@dataclass
class ClassifyResult:
    intent: str
    confidence: float
    label: str  # safe / dangerous

class IntentClassifier:
    """Layer 2: 轻量分类器 — 快速意图分类"""

    # 危险关键词权重（简化版 FastText 思路）
    KEYWORD_WEIGHTS: dict[str, dict[str, float]] = {
        "drop_table":     {"drop": 0.4, "table": 0.3, "delete": 0.2, "remove": 0.1},
        "delete_all":     {"delete": 0.3, "all": 0.2, "remove": 0.2, "clear": 0.2, "wipe": 0.1},
        "execute_shell":  {"shell": 0.3, "exec": 0.2, "command": 0.2, "run": 0.1, "bash": 0.2},
        "ssh_connect":    {"ssh": 0.4, "remote": 0.2, "connect": 0.2, "server": 0.1, "login": 0.1},
        "send_email":     {"email": 0.3, "send": 0.2, "mail": 0.2, "smtp": 0.2, "notify": 0.1},
        "access_secret":  {"secret": 0.3, "key": 0.2, "password": 0.2, "credential": 0.2, "token": 0.1},
        "modify_system":  {"system": 0.2, "config": 0.2, "modify": 0.2, "change": 0.1, "update": 0.1},
        "network_request": {"fetch": 0.2, "request": 0.2, "api": 0.2, "http": 0.2, "call": 0.2},
    }

    def __init__(self, intent_registry):
        self.weights = dict(self.KEYWORD_WEIGHTS)

    def classify(self, output: str) -> ClassifyResult:
        """基于加权的词袋分类"""
        words = output.lower().split()
        best_intent = "safe"
        best_score = 0.0

        for intent, kw_weights in self.weights.items():
            score = sum(kw_weights.get(w, 0) for w in words)
            if score > best_score:
                best_score = score
                best_intent = intent

        # 归一化置信度
        confidence = min(best_score, 1.0)

        return ClassifyResult(
            intent=best_intent if confidence >= 0.5 else "safe",
            confidence=confidence,
            label="dangerous" if confidence >= 0.5 else "safe",
        )
```

### 3.5 Policy Guard 实现

```python
import json
import yaml
from typing import Union, Optional
from agentguard.policy.parser import PolicyParser
from agentguard.policy.engine import RuleEngine
from agentguard.result import CheckResult, GuardLevel

class PolicyGuard:
    """策略守卫 — 基于规则的访问控制和合规检查"""

    def __init__(self, policy: Union[str, dict]):
        if isinstance(policy, str):
            if policy.endswith(('.yaml', '.yml')):
                with open(policy) as f:
                    policy_dict = yaml.safe_load(f)  # safe_load 防止代码注入
            else:
                policy_dict = yaml.safe_load(policy)
        else:
            policy_dict = policy

        # 校验策略文件结构
        self._validate_policy(policy_dict)

        self.defaults = policy_dict.get("defaults", {
            "on_no_match": "allow",
            "on_error": "pass",
        })
        self.rules = PolicyParser.parse(policy_dict)
        self.engine = RuleEngine(self.rules)

    def check(self, output: str, context: dict) -> CheckResult:
        """策略校验"""
        import time
        start = time.monotonic()

        # 解析 output 为结构化数据（如果可以）
        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            data = {"raw": output}

        # 规则引擎匹配
        try:
            match = self.engine.evaluate(data, context)
        except Exception as e:
            # 规则引擎出错 → 按 defaults.on_error 处理
            on_error = self.defaults.get("on_error", "pass")
            return CheckResult(
                layer="policy",
                passed=on_error == "pass",
                level=GuardLevel.WARN if on_error == "pass" else GuardLevel.DENY,
                message=f"策略引擎执行错误: {e}",
                details={"error": str(e)},
                duration_ms=(time.monotonic() - start) * 1000,
            )

        if match is None:
            # 无规则命中 → 按 defaults.on_no_match 处理
            on_no_match = self.defaults.get("on_no_match", "allow")
            if on_no_match == "allow":
                return CheckResult(
                    layer="policy",
                    passed=True,
                    level=GuardLevel.PASS,
                    message="无策略命中，默认放行",
                    duration_ms=(time.monotonic() - start) * 1000,
                )
            else:
                return CheckResult(
                    layer="policy",
                    passed=False,
                    level=GuardLevel.DENY,
                    message="无策略命中，默认拦截",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        action = match["action"]
        if action == "deny":
            return CheckResult(
                layer="policy",
                passed=False,
                level=GuardLevel.DENY,
                message=match.get("message", f"策略拦截: {match['name']}"),
                details={"rule": match["name"], "action": "deny"},
                duration_ms=(time.monotonic() - start) * 1000,
            )
        elif action == "ask_human":
            return CheckResult(
                layer="policy",
                passed=False,
                level=GuardLevel.ASK_HUMAN,
                message=match.get("message", "需要人工确认"),
                details={
                    "rule": match["name"],
                    "action": "ask_human",
                    "timeout": match.get("timeout", 300),
                    "fallback": match.get("fallback", "deny"),
                },
                duration_ms=(time.monotonic() - start) * 1000,
            )
        elif action == "modify":
            return CheckResult(
                layer="policy",
                passed=True,
                level=GuardLevel.FIX,
                message=match.get("message", "策略自动修正"),
                details={"rule": match["name"], "action": "modify"},
                fix=match.get("modified_output"),
                duration_ms=(time.monotonic() - start) * 1000,
            )
        else:  # allow
            return CheckResult(
                layer="policy",
                passed=True,
                level=GuardLevel.PASS,
                message=f"策略放行: {match['name']}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

    @staticmethod
    def _validate_policy(policy: dict):
        """校验策略文件结构"""
        if "rules" not in policy:
            raise ValueError("策略文件必须包含 'rules' 字段")
        for rule in policy["rules"]:
            if "name" not in rule:
                raise ValueError("每条规则必须包含 'name'")
            if "condition" not in rule:
                raise ValueError(f"规则 '{rule.get('name', '?')}' 必须包含 'condition'")
            if "action" not in rule:
                raise ValueError(f"规则 '{rule['name']}' 必须包含 'action'")
            if rule["action"] not in ("allow", "deny", "modify", "ask_human"):
                raise ValueError(f"规则 '{rule['name']}' 的 action 必须是 allow/deny/modify/ask_human")
```

---

## 四、协议适配层详细设计

### 4.1 MCP Server

**架构**：Node.js 进程，通过 stdin/stdout 与 IDE 通信。

```json
// Cursor / Claude Code / Copilot 配置示例
{
  "mcpServers": {
    "agentguard": {
      "command": "npx",
      "args": ["-y", "agentguard-mcp@latest"],
      "env": {
        "AGENTGUARD_POLICY": "/path/to/policy.yaml",
        "AGENTGUARD_SEMANTIC": "rule"
      }
    }
  }
}
```

**MCP Tools 暴露**：

| Tool | 功能 | 参数 |
|:---|:---|:---|
| `guard_validate` | 校验一段 AI 输出 | `output: string`, `context?: object` |
| `guard_set_policy` | 动态更新策略 | `policy: string` (YAML) |
| `guard_get_audit` | 查询审计日志 | `limit?: number`, `level?: string` |
| `guard_status` | 查看当前配置和状态 | — |
| `guard_add_intent` | 添加自定义危险意图 | `name: string`, `patterns?: string[]` |

**MCP Resources 暴露**：

| Resource | 功能 | URI |
|:---|:---|:---|
| 当前策略 | 读取当前生效的策略 | `agentguard://policy` |
| 审计统计 | 读取拦截/放行统计 | `agentguard://stats` |

### 4.2 LSP Server

**架构**：TypeScript 进程，与编辑器通过 JSON-RPC 2.0 通信。

**核心能力**：

1. **实时诊断**：对 AI 生成的代码/文本进行安全标注（LSP Diagnostics）
2. **Code Action**：提供快速修正建议（替换/注释/删除）
3. **Hover 信息**：悬停查看 Guard 判断原因
4. **Code Lens**：在 AI 输出上方显示安全状态标签

**触发机制**：

| 事件 | 行为 |
|:---|:---|
| `textDocument/didChange` | 对变更内容进行增量校验 |
| `textDocument/didOpen` | 对文档进行全量校验 |
| `textDocument/codeAction` | 提供修正建议 |
| 自定义 `agentguard/validate` | 手动触发校验 |

**诊断信息映射**：

```typescript
// GuardLevel → LSP DiagnosticSeverity 映射
const severityMap = {
  DENY: DiagnosticSeverity.Error,        // 红色波浪线
  WARN: DiagnosticSeverity.Warning,      // 黄色波浪线
  FIX: DiagnosticSeverity.Information,   // 蓝色波浪线（已修正）
  ASK_HUMAN: DiagnosticSeverity.Warning, // 黄色波浪线 + 问号图标
  PASS: null,                            // 无标注
};
```

**VS Code 扩展 manifest 片段**：

```json
{
  "contributes": {
    "languages": [
      { "id": "agentguard-policy", "extensions": [".agpolicy.yaml", ".agpolicy.yml"] }
    ],
    "commands": [
      { "command": "agentguard.validate", "title": "AI Output Guard: Validate Selection" },
      { "command": "agentguard.showAudit", "title": "AI Output Guard: Show Audit Log" }
    ],
    "configuration": {
      "title": "AI Output Guard",
      "properties": {
        "agentguard.policyPath": { "type": "string", "default": "" },
        "agentguard.semanticMode": { "type": "string", "enum": ["auto","rule","classifier","embedding"], "default": "rule" },
        "agentguard.enableDiagnostics": { "type": "boolean", "default": true }
      }
    }
  }
}
```

### 4.3 CLI

```bash
# 校验一段输出
agentguard check '{"endpoint": "/prod/db", "method": "DELETE"}'

# 指定策略文件
agentguard check --policy ./policy.yaml '{"action": "drop table users"}'

# 管道模式（适合 CI/CD）
cat llm_output.json | agentguard check --stdin

# 指定 Schema 文件
agentguard check --schema ./schema.json llm_output.json

# 只启用特定层
agentguard check --layers schema,policy --policy ./policy.yaml llm_output.json

# 输出格式
agentguard check --format json llm_output.json     # JSON 输出
agentguard check --format yaml llm_output.json     # YAML 输出
agentguard check --format table llm_output.json    # 表格输出

# 启动守护进程模式（供其他工具调用）
agentguard daemon --port 8765

# 配置管理
agentguard config init                     # 初始化配置文件
agentguard config set policy.path ./policy.yaml
agentguard config set semantic.mode rule

# 查看审计日志
agentguard audit list --limit 20
agentguard audit show <audit-id>
```

**退出码**：

| 退出码 | 含义 |
|:---|:---|
| 0 | 校验通过（PASS/FIX/WARN） |
| 1 | 校验拦截（DENY） |
| 2 | 需人工确认（ASK_HUMAN） |
| 3 | Guard 内部错误 |

### 4.4 API Proxy

```
┌──────────┐    HTTP     ┌──────────────┐    HTTP    ┌──────────┐
│ AI 工具   │───────────▶│ AI Output Guard   │──────────▶│ LLM API  │
│(Cursor等) │            │ API Proxy    │           │(OpenAI等) │
└──────────┘            └──────┬───────┘           └──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 1. 识别 LLM API 请求 │  → URL 匹配 + Content-Type
                    │ 2. 转发给 LLM       │  → 原样转发
                    │ 3. 解析 LLM 响应    │  → 提取输出文本
                    │ 4. Guard 校验响应    │  → 三层校验
                    │ 5. 返回校验后结果    │  → 修改/拦截/放行
                    └─────────────────────┘
```

**LLM API 识别规则**：

| 模式 | URL 匹配 | 提取位置 |
|:---|:---|:---|
| OpenAI Chat | `api.openai.com/v1/chat/completions` | `response.choices[0].message.content` |
| OpenAI Completions | `api.openai.com/v1/completions` | `response.choices[0].text` |
| Anthropic | `api.anthropic.com/v1/messages` | `response.content[0].text` |
| 通义千问 | `dashscope.aliyuncs.com/*/completions` | `response.output.text` |
| 自定义 | 用户配置正则 | 用户配置 JSONPath |

**拦截行为**：

| 校验结果 | Proxy 行为 |
|:---|:---|
| PASS | 原样返回 LLM 响应 |
| FIX | 替换 LLM 输出为修正后内容，添加 `X-AI Output Guard-Fix` header |
| WARN | 原样返回，添加 `X-AI Output Guard-Warning` header |
| DENY | 返回 HTTP 200 但替换内容为安全提示，添加 `X-AI Output Guard-Blocked` header |
| ASK_HUMAN | 返回 HTTP 202（需要确认），Body 含确认信息 |

**部署方式**：

```bash
# Docker 一键部署
docker run -d \
  -p 8080:8080 \
  -v ./policy.yaml:/app/policy.yaml \
  -e AGENTGUARD_POLICY=/app/policy.yaml \
  -e AGENTGUARD_SEMANTIC_MODE=rule \
  ai-output-guard/proxy:latest

# 客户端配置（零代码）
export HTTP_PROXY=http://localhost:8080
export HTTPS_PROXY=http://localhost:8080
# 之后所有 AI 工具的请求自动经过 Guard

# 健康检查
curl http://localhost:8080/health
# → {"status": "healthy", "version": "0.1.0", "uptime_seconds": 3600}
```

---

## 五、数据流

### 5.1 核心校验流程

```
LLM 输出（string）
       │
       ▼
  ┌─────────────┐   失败   ┌──────────────┐
  │ Schema Guard │────────▶│ 可自动修正？    │
  │ 结构校验     │         │ 是 → 修正+继续 │
  └──────┬──────┘         │ 否 → DENY     │
         │ 通过            └──────────────┘
         ▼
  ┌─────────────┐
  │Semantic Guard│   规则命中   ┌─────────────┐
  │ 语义校验     │───────────▶│ DENY        │
  │              │           │ (置信度=1.0) │
  │              ├─分类器命中─▶│ DENY/WARN   │
  │              │           │ (高置信度)    │
  │              ├─Embedding─▶│ WARN        │
  │              │           │ (中置信度)    │
  └──────┬──────┘           └─────────────┘
         │ 通过
         ▼
  ┌─────────────┐
  │ Policy Guard │   deny   ┌─────────────┐
  │ 策略校验     │────────▶│ DENY        │
  └──────┬──────┘   ask     │ ask_human →  │
         │ 通过    │       │ 等待人工确认  │
         │        allow    └─────────────┘
         ▼
  ┌─────────────┐
  │ Audit Logger │
  │ 审计记录     │
  └──────┬──────┘
         │
         ▼
   GuardResult
   (level, output, checks, audit_id, duration_ms)
```

### 5.2 API Proxy 数据流

```
客户端请求
       │
       ▼
  ┌─────────────┐
  │ URL 匹配     │  → 是否为已知的 LLM API？
  └──────┬──────┘
         │ 否 → 直接转发（不校验）
         │ 是
         ▼
  ┌─────────────┐
  │ 转发请求     │  → 原样转发给 LLM API（超时 30s）
  └──────┬──────┘
         │ LLM 响应
         ▼
  ┌─────────────┐
  │ 提取输出     │  → 按 JSONPath 提取文本内容
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ Guard 校验   │  → 三层校验
  └──────┬──────┘
         │
    ┌────┴────┐
    │         │
  PASS/FIX  DENY/WARN/ASK
    │         │
    ▼         ▼
  修改响应   替换内容+Header
  (或原样)   (X-AI Output Guard-*)
```

---

## 六、集成示例

### 6.1 集成到 openclaw / hermes

```python
from agentguard import Guard, GuardLevel
from pydantic import BaseModel

class AgentAction(BaseModel):
    action: str
    target: str
    params: dict = {}

guard = Guard(
    schema=AgentAction,
    semantic=True,
    semantic_mode="rule",              # 规则模式，零延迟
    dangerous_intents=["execute_shell", "drop_table"],
    policy="policies/agent.yaml",
    on_fail="deny",
    auto_fix=True,
)

async def agent_step(prompt: str) -> AgentAction:
    raw_output = await llm.generate(prompt)
    result = guard.validate(raw_output, context={"agent": "openclaw"})

    if result.level == GuardLevel.DENY:
        logger.warning(f"AI Output Guard 拦截: {result.blocked_by} - {result.checks[-1].message}")
        return AgentAction(action="blocked", target="", params={"reason": result.checks[-1].message})
    elif result.level == GuardLevel.FIX:
        logger.info(f"AI Output Guard 自动修正: {result.checks[0].message}")
        return AgentAction.model_validate_json(result.output)
    elif result.level == GuardLevel.ASK_HUMAN:
        # 在 Agent 循环中，可以回退到安全动作
        logger.warning(f"AI Output Guard 需人工确认: {result.checks[-1].message}")
        return AgentAction(action="pending_approval", target="", params={"reason": result.checks[-1].message})
    else:
        return AgentAction.model_validate_json(result.output)
```

### 6.2 集成到 LangChain

```python
from langchain_core.output_parsers import PydanticOutputParser, OutputParserException
from agentguard import Guard, GuardLevel

class GuardedOutputParser(PydanticOutputParser):
    """LangChain 输出解析器 + AI Output Guard 安全校验"""

    def __init__(self, pydantic_object, **guard_kwargs):
        super().__init__(pydantic_object=pydantic_object)
        self.guard = Guard(schema=pydantic_object, **guard_kwargs)

    def parse(self, text: str):
        result = self.guard.validate(text)
        if result.level == GuardLevel.DENY:
            raise OutputParserException(
                f"AI Output Guard 拦截: {result.blocked_by} — {result.checks[-1].message}"
            )
        return super().parse(result.output or text)
```

### 6.3 集成到 CI/CD

```yaml
# .github/workflows/agent-guard.yml
name: Agent Output Guard
on: [pull_request]

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install AI Output Guard
        run: pip install ai-output-guard
      - name: Check AI-generated files
        run: |
          # 检查 AI 生成的配置文件
          for f in $(git diff --name-only --diff-filter=A origin/main | grep '.ai/'); do
            agentguard check --policy ./policy.yaml --format json "$f" || exit 1
          done
```

---

## 七、审计系统

### 7.1 审计日志结构

```python
@dataclass
class AuditEntry:
    audit_id: str                # 唯一 ID
    timestamp: float             # 时间戳
    raw_output: str              # 原始 LLM 输出
    final_output: Optional[str]  # 最终输出
    level: GuardLevel            # 最终判定
    blocked_by: Optional[str]    # 拦截层
    checks: list[CheckResult]    # 各层校验结果
    context: dict                # 上下文信息
    policy_version: Optional[str]  # 策略版本
    hash: str                    # 哈希链（防篡改）
    prev_hash: str               # 前一条日志的哈希
```

### 7.2 哈希链防篡改

```python
import hashlib

class HashChainAuditStore:
    """哈希链审计存储 — 借鉴 Authensor 的防篡改设计"""

    def __init__(self):
        self._prev_hash = "0" * 64  # 创世哈希

    def append(self, entry: AuditEntry) -> str:
        """追加审计条目，返回当前哈希"""
        content = f"{entry.audit_id}{entry.timestamp}{entry.raw_output}{entry.level.value}{self._prev_hash}"
        current_hash = hashlib.sha256(content.encode()).hexdigest()

        entry.prev_hash = self._prev_hash
        entry.hash = current_hash
        self._prev_hash = current_hash

        return current_hash

    def verify(self, entries: list[AuditEntry]) -> bool:
        """验证审计链完整性"""
        prev = "0" * 64
        for entry in entries:
            content = f"{entry.audit_id}{entry.timestamp}{entry.raw_output}{entry.level.value}{prev}"
            expected = hashlib.sha256(content.encode()).hexdigest()
            if entry.hash != expected or entry.prev_hash != prev:
                return False
            prev = entry.hash
        return True
```

### 7.3 存储后端

| 后端 | 适用场景 | 配置 |
|:---|:---|:---|
| **内存** | 开发/测试 | 默认 |
| **本地文件** | 单机部署 | `audit.store=file`, `audit.path=./audit.log` |
| **SQLite** | 小团队 | `audit.store=sqlite`, `audit.path=./audit.db` |
| **远程 API** | 企业部署 | `audit.store=remote`, `audit.url=https://audit.example.com` |

---

## 八、错误处理与降级策略

### 8.1 错误层级

| 错误类型 | 处理方式 | 示例 |
|:---|:---|:---|
| **输入错误** | 返回 DENY + 明确错误信息 | JSON 解析失败、Schema 未定义 |
| **校验超时** | 按 on_error 配置降级 | Embedding 模型推理超时 |
| **引擎错误** | 按 on_error 配置降级 + 告警 | 规则引擎异常、分类器加载失败 |
| **系统错误** | Fail-Open + 告警 | 内存不足、文件系统错误 |

### 8.2 降级链

```
Semantic Guard 降级链:
  Embedding 模式 → 分类器模式 → 规则模式 → 跳过语义校验(WARN)

Policy Guard 降级链:
  自定义规则 → 内置默认规则 → on_no_match 配置 → allow(WARN)

API Proxy 降级链:
  Guard 校验 → 超时/错误 → 原样转发(透明代理) + X-AI Output Guard-Error header
```

### 8.3 统一异常定义

```python
class GuardError(Exception):
    """Guard 基础异常"""
    def __init__(self, message: str, layer: str = ""):
        self.layer = layer
        super().__init__(message)

class GuardTimeoutError(GuardError):
    """校验超时"""
    pass

class SchemaValidationError(GuardError):
    """Schema 校验错误"""
    pass

class PolicyLoadError(GuardError):
    """策略加载错误"""
    pass

class EmbeddingModelError(GuardError):
    """Embedding 模型错误"""
    pass
```

---

## 九、配置管理

### 9.1 配置来源优先级（高→低）

1. 代码中直接传入的参数
2. 环境变量（`AGENTGUARD_*`）
3. 项目配置文件（`.agentguard.yaml`）
4. 全局配置文件（`~/.agentguard/config.yaml`）
5. 内置默认值

### 9.2 配置文件示例

```yaml
# .agentguard.yaml — 项目级配置
guard:
  on_fail: deny
  on_error: pass
  auto_fix: true
  audit: true

  semantic:
    mode: rule            # auto/rule/classifier/embedding
    threshold: 0.85
    dangerous_intents:
      - drop_table
      - execute_shell
      - access_secret

  policy:
    path: ./policy.yaml
    watch: true           # 监听策略文件变更，自动热更新
    reload_interval: 30   # 热更新检查间隔（秒）

  audit:
    store: file
    path: ./audit.log
    hash_chain: true      # 启用哈希链防篡改

  timeout:
    schema: 100           # ms
    semantic: 500
    policy: 200
```

### 9.3 热更新机制

```python
import hashlib
import time

class PolicyWatcher:
    """策略文件热更新监听"""

    def __init__(self, path: str, callback, interval: int = 30):
        self.path = path
        self.callback = callback
        self.interval = interval
        self._last_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        with open(self.path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def check(self) -> bool:
        """检查策略文件是否变更"""
        current_hash = self._compute_hash()
        if current_hash != self._last_hash:
            self._last_hash = current_hash
            self.callback(self.path)
            return True
        return False
```

---

## 十、安全考量

### 10.1 Guard 自身安全

| 威胁 | 缓解措施 |
|:---|:---|
| **策略文件注入** | `yaml.safe_load` 禁止任意 Python 对象；策略校验器检查非法字段 |
| **正则 DoS** | 规则匹配器限制正则复杂度；超时保护；禁止回溯型正则 |
| **审计日志篡改** | 哈希链校验；日志只追加不修改 |
| **LLM 输出注入 Guard** | Guard 输入为纯字符串，不执行任何动态代码；所有输出经过转义 |
| **API Proxy MITM** | Proxy 不做 TLS 终止；用户负责 TLS；健康检查端点只读 |

### 10.2 数据隐私

- 审计日志默认不含 PII（可配置脱敏规则）
- API Proxy 不持久化请求/响应（仅记录 Guard 判定）
- Embedding 计算默认本地执行（不上传数据到第三方）
- LLM-as-Judge 模式明确告知用户数据会发送到 LLM API

---

## 十一、部署架构

### 11.1 开发模式

```bash
# 本地开发
pip install ai-output-guard
# 或
pip install ai-output-guard[semantic]  # 含 Embedding 模型
```

### 11.2 团队部署

```bash
# API Proxy + Dashboard
docker compose up -d

# docker-compose.yml
version: "3.8"
services:
  proxy:
    image: ai-output-guard/proxy:latest
    ports:
      - "8080:8080"
    volumes:
      - ./policy.yaml:/app/policy.yaml
    environment:
      - AGENTGUARD_POLICY=/app/policy.yaml
      - AGENTGUARD_AUDIT_STORE=sqlite
      - AGENTGUARD_AUDIT_PATH=/data/audit.db
    volumes:
      - audit-data:/data

  dashboard:
    image: ai-output-guard/dashboard:latest
    ports:
      - "3000:3000"
    environment:
      - AGENTGUARD_API_URL=http://proxy:8080

volumes:
  audit-data:
```

### 11.3 企业部署

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ 开发者 IDE   │────▶│ API Proxy    │────▶│ LLM APIs     │
│ (MCP/LSP)   │     │ (K8s Pod)    │     │ (OpenAI等)   │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────▼───────┐
                    │ Audit Store  │
                    │ (PostgreSQL) │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Dashboard    │
                    │ (Web UI)     │
                    └──────────────┘
```

- API Proxy 部署为 K8s Deployment（2+ 副本，滚动更新）
- Audit Store 使用 PostgreSQL（持久化+备份）
- Dashboard 前端 Nginx + 后端 FastAPI
- 策略文件通过 ConfigMap 管理，热更新通过文件监听

---

## 十二、测试策略

### 12.1 测试分层

| 层级 | 覆盖范围 | 工具 | 目标覆盖率 |
|:---|:---|:---|:---|
| **单元测试** | 每个 Guard 类、修正器、运算符 | pytest | > 90% |
| **集成测试** | 三层组合、配置加载、降级链 | pytest + fixtures | > 80% |
| **协议测试** | MCP/LSP/CLI/Proxy 各协议 | 专项测试套件 | > 80% |
| **性能测试** | 延迟、吞吐、内存 | locust + memory_profiler | 关键路径 |
| **安全测试** | 注入、DoS、篡改 | 自定义 + bandit | 无高危漏洞 |
| **端到端测试** | 从 IDE 到 Guard 到 审计的完整链路 | Playwright | 关键路径 |

### 12.2 关键测试场景

```python
# test_schema_guard.py
class TestSchemaGuard:
    def test_valid_json_passes(self): ...
    def test_invalid_json_denied(self): ...
    def test_enum_typo_auto_fixed(self): ...
    def test_type_coercion(self): ...
    def test_missing_optional_field_gets_default(self): ...
    def test_extra_field_stripped_in_lenient_mode(self): ...
    def test_extra_field_denied_in_strict_mode(self): ...

# test_semantic_guard.py
class TestSemanticGuard:
    def test_rule_drop_table_detected(self): ...
    def test_rule_rm_rf_detected(self): ...
    def test_classifier_dangerous_intent(self): ...
    def test_benign_output_passes(self): ...
    def test_false_positive_rate_acceptable(self): ...
    def test_degradation_to_rule_mode(self): ...

# test_policy_guard.py
class TestPolicyGuard:
    def test_deny_rule_blocks(self): ...
    def test_ask_human_returns_awaiting(self): ...
    def test_allow_rule_passes(self): ...
    def test_priority_ordering(self): ...
    def test_condition_operators(self): ...
    def test_policy_yaml_injection_prevented(self): ...
    def test_hot_reload(self): ...

# test_guard_integration.py
class TestGuardIntegration:
    def test_three_layers_pass(self): ...
    def test_schema_fix_then_pass(self): ...
    def test_semantic_blocks_after_schema_pass(self): ...
    def test_policy_ask_human_flow(self): ...
    def test_timeout_degradation(self): ...
    def test_error_degradation(self): ...
```

---

## 十三、性能优化

### 13.1 缓存策略

| 缓存目标 | 策略 | 命中率预期 |
|:---|:---|:---|
| Schema 校验结果（相同输出） | LRU Cache（1024 条） | 高（Agent 常有重复输出） |
| Embedding 向量 | LRU Cache（512 条） | 中（相似输出命中） |
| 分类器结果 | LRU Cache（1024 条） | 高 |
| 策略编译结果 | 进程生命周期缓存 | 100%（策略不频繁变更） |

### 13.2 异步支持

```python
import asyncio
import aiohttp
from agentguard import Guard, GuardResult

class AsyncGuard(Guard):
    """Guard 的异步版本 — Embedding 和 LLM-as-Judge 使用 aiohttp"""

    async def validate(self, output: str, context: Optional[dict] = None) -> GuardResult:
        """异步校验"""
        result = GuardResult(raw=output)
        current_output = output

        try:
            # Schema Guard（同步，延迟极低）
            if self.schema_guard:
                sr = self.schema_guard.check(current_output)
                result.add_check("schema", sr)
                if not sr.passed:
                    if self.auto_fix and sr.fix:
                        current_output = sr.fix
                        result.output = current_output
                    else:
                        return result.finalize(on_fail=self.on_fail)

            # Semantic Guard（异步：Embedding + LLM-as-Judge）
            if self.semantic_guard:
                sr = await self._async_semantic_check(current_output)
                result.add_check("semantic", sr)
                if not sr.passed:
                    return result.finalize(on_fail=self.on_fail)

            # Policy Guard（同步）
            if self.policy_guard:
                sr = self.policy_guard.check(current_output, context or {})
                result.add_check("policy", sr)
                if not sr.passed:
                    return result.finalize(on_fail=self.on_fail)

        except GuardTimeoutError as e:
            result.add_check("timeout", CheckResult(
                layer="timeout", passed=True, level=GuardLevel.WARN,
                message=f"校验超时: {e.layer}，已降级放行",
            ))
        except GuardError as e:
            result.add_check("error", CheckResult(
                layer="error", passed=self.on_error == "pass",
                level=GuardLevel.WARN if self.on_error == "pass" else GuardLevel.DENY,
                message=f"Guard 内部错误: {e}",
            ))

        return result.finalize(on_fail=self.on_fail)

    async def _async_semantic_check(self, output: str) -> CheckResult:
        """异步语义校验 — Embedding 和 LLM-as-Judge 用 aiohttp"""
        # 规则模式：同步执行（零延迟）
        rule_result = self.semantic_guard.rule_matcher.match(output)
        if rule_result.matched:
            return CheckResult(
                layer="semantic", passed=False, level=GuardLevel.DENY,
                message=f"语义匹配到危险意图: {rule_result.intent}（规则命中）",
                confidence=1.0,
            )

        # 分类器模式：同步执行（低延迟）
        if self.semantic_guard.classifier:
            cls_result = self.semantic_guard.classifier.classify(output)
            if cls_result.confidence >= self.semantic_guard.threshold:
                level = GuardLevel.DENY if cls_result.confidence >= 0.95 else GuardLevel.WARN
                return CheckResult(
                    layer="semantic", passed=False, level=level,
                    message=f"语义匹配到危险意图: {cls_result.intent}（分类器）",
                    confidence=cls_result.confidence,
                )

        # Embedding 模式：异步执行
        if self.semantic_guard._embedder:
            emb_result = await self.semantic_guard._embedder.async_match(output)
            if emb_result.similarity >= self.semantic_guard.threshold:
                return CheckResult(
                    layer="semantic", passed=False, level=GuardLevel.WARN,
                    message=f"语义近似危险意图: {emb_result.intent}（Embedding）",
                    confidence=emb_result.similarity,
                )

        return CheckResult(
            layer="semantic", passed=True, level=GuardLevel.PASS,
            message="语义校验通过",
        )

    async def validate_batch(self, outputs: list[str], context: Optional[dict] = None) -> list[GuardResult]:
        """异步批量校验 — 并发执行，共享 Embedding 计算"""
        tasks = [self.validate(output, context) for output in outputs]
        return await asyncio.gather(*tasks)
```

### 13.3 批处理

```python
class Guard:
    def validate_batch(self, outputs: list[str], context: Optional[dict] = None) -> list[GuardResult]:
        """批量校验 — 共享 Embedding 计算"""
        results = []
        # 预计算所有 Embedding（单次批量推理）
        if self.semantic_guard and self.semantic_guard._embedder:
            all_embeddings = self.semantic_guard._embedder.embed_batch(outputs)
        else:
            all_embeddings = None

        for i, output in enumerate(outputs):
            # 临时注入预计算的 Embedding
            if all_embeddings:
                self.semantic_guard._cached_embedding = all_embeddings[i]
            results.append(self.validate(output, context))

        return results
```

### 13.4 装饰器模式

```python
import functools
from typing import Callable, Optional

def guarded(
    schema: Optional[Union[type[BaseModel], dict]] = None,
    semantic: bool = False,
    semantic_mode: str = "auto",
    dangerous_intents: Optional[list[str]] = None,
    policy: Optional[Union[str, dict]] = None,
    on_fail: str = "deny",
    auto_fix: bool = True,
    **guard_kwargs,
):
    """装饰器：自动校验函数返回值

    用法：
        @guarded(schema=AgentAction, semantic=True, policy="policy.yaml")
        async def call_llm(prompt: str) -> str:
            return await llm.generate(prompt)

        result = await call_llm("Delete all users")
        # result 是 GuardResult，不是 str
    """
    guard = Guard(
        schema=schema,
        semantic=semantic,
        semantic_mode=semantic_mode,
        dangerous_intents=dangerous_intents,
        policy=policy,
        on_fail=on_fail,
        auto_fix=auto_fix,
        **guard_kwargs,
    )

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                raw_output = await func(*args, **kwargs)
                return guard.validate(raw_output)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                raw_output = func(*args, **kwargs)
                return guard.validate(raw_output)
            return sync_wrapper

    return decorator
```

### 13.5 上下文管理器

```python
from contextlib import contextmanager

@contextmanager
def GuardContext(
    schema: Optional[Union[type[BaseModel], dict]] = None,
    semantic: bool = False,
    policy: Optional[Union[str, dict]] = None,
    on_fail: str = "deny",
    **guard_kwargs,
):
    """上下文管理器：创建临时 Guard 会话

    用法：
        with GuardContext(schema=AgentAction, semantic=True) as guard:
            raw = llm.generate(prompt)
            result = guard.validate(raw)
            if result.is_safe:
                process(result.output)
    """
    guard = Guard(
        schema=schema,
        semantic=semantic,
        policy=policy,
        on_fail=on_fail,
        **guard_kwargs,
    )
    try:
        yield guard
    finally:
        # 会话结束，写入审计日志汇总
        if guard.audit and guard._audit_logger:
            guard._audit_logger.flush()
```

### 13.6 插件系统

```python
from typing import Protocol

class BaseGuard(Protocol):
    """自定义 Guard 层协议"""
    name: str

    def check(self, output: str) -> CheckResult:
        ...

class GuardRegistry:
    """Guard 注册表 — 管理自定义 Guard 层和策略动作"""

    def __init__(self):
        self._custom_guards: list[BaseGuard] = []
        self._action_handlers: dict[str, ActionHandler] = {}

    def register_guard(self, guard: BaseGuard):
        """注册自定义 Guard 层"""
        self._custom_guards.append(guard)

    def register_action(self, handler: ActionHandler):
        """注册自定义策略动作处理器"""
        self._action_handlers[handler.action_type] = handler

    def load_plugins(self):
        """从 entry_points 加载已安装的插件"""
        import importlib.metadata

        # 加载 Guard 插件
        for ep in importlib.metadata.entry_points(group="agentguard.guards"):
            guard_cls = ep.load()
            self.register_guard(guard_cls())

        # 加载 Action 插件
        for ep in importlib.metadata.entry_points(group="agentguard.actions"):
            handler_cls = ep.load()
            self.register_action(handler_cls())


# Guard 类中的插件集成
class Guard:
    def __init__(self, ..., plugins: bool = True):
        self.registry = GuardRegistry()
        if plugins:
            self.registry.load_plugins()

    def add_guard(self, guard: BaseGuard):
        """添加自定义 Guard 层到校验流水线"""
        self.registry.register_guard(guard)

    def validate(self, output: str, context: Optional[dict] = None) -> GuardResult:
        result = GuardResult(raw=output)

        # 内置三层
        # ... (Schema / Semantic / Policy)

        # 自定义 Guard 层
        for custom_guard in self.registry._custom_guards:
            sr = custom_guard.check(current_output)
            result.add_check(custom_guard.name, sr)
            if not sr.passed:
                return result.finalize(on_fail=self.on_fail)

        return result.finalize(on_fail=self.on_fail)
```

---

## 十四、依赖与技术栈

### 14.1 核心引擎

| 依赖 | 用途 | 版本 | 安装条件 |
|:---|:---|:---|:---|
| Python | 运行时 | 3.10+ | 必须 |
| pydantic | Schema 校验 + 数据模型 | v2 | 必须 |
| jsonschema | JSON Schema 校验 | ≥4.0 | 必须 |
| PyYAML | 策略文件解析 | ≥6.0 | 必须 |
| numpy | 向量计算 | ≥1.24 | 可选（embedding模式） |
| sentence-transformers | 本地 embedding 模型 | ≥2.2 | 可选（`pip install ai-output-guard[semantic]`） |
| fasttext-wheel | 轻量分类器 | ≥0.9.2 | 可选（`pip install ai-output-guard[classifier]`） |

### 14.2 协议层

| 依赖 | 用途 | 版本 |
|:---|:---|:---|
| Node.js | MCP/LSP Server 运行时 | 18+ |
| @modelcontextprotocol/sdk | MCP 协议 SDK | latest |
| vscode-languageserver | LSP 协议 SDK | latest |
| Click / Typer | CLI 框架 | latest |
| FastAPI + httpx | API Proxy | latest |
| uvicorn | ASGI 服务器 | latest |

### 14.3 Dashboard（Phase 4）

| 依赖 | 用途 |
|:---|:---|
| FastAPI | 后端 API |
| Vue 3 + Vite | 前端框架 |
| TailwindCSS | UI 样式 |
| SQLite / PostgreSQL | 审计日志存储 |

### 14.4 开发/测试

| 依赖 | 用途 |
|:---|:---|
| pytest | 单元/集成测试 |
| pytest-asyncio | 异步测试 |
| pytest-cov | 覆盖率 |
| locust | 性能测试 |
| bandit | 安全扫描 |
| ruff | Lint + Format |

---

## 十五、项目结构总览

```
agentguard/
├── docs/                          # 文档
│   ├── 01-PRODUCT-DEFINITION.md   # 产品定义（v2.0）
│   ├── 02-ARCHITECTURE.md         # 架构设计（v2.0，本文件）
│   ├── 03-API-REFERENCE.md        # 公开 API 参考
│   ├── 04-POLICY-TEMPLATES.md     # 实战策略模板
│   ├── 05-PROTOCOL-FLOWS.md       # 协议交互流程
│   └── 06-EVALUATION.md           # 评估与调优框架
├── packages/
│   ├── core/                      # Python SDK（agentguard）
│   │   ├── pyproject.toml
│   │   ├── src/agentguard/        # 核心引擎源码
│   │   │   ├── __init__.py
│   │   │   ├── guard.py
│   │   │   ├── schema_guard.py
│   │   │   ├── semantic_guard.py
│   │   │   ├── policy_guard.py
│   │   │   ├── result.py
│   │   │   ├── errors.py
│   │   │   ├── registry.py
│   │   │   ├── config.py
│   │   │   ├── audit/
│   │   │   ├── semantic/
│   │   │   ├── policy/
│   │   │   ├── fix/
│   │   │   └── plugins/
│   │   └── tests/
│   │       ├── test_schema_guard.py
│   │       ├── test_semantic_guard.py
│   │       ├── test_policy_guard.py
│   │       └── test_guard_integration.py
│   ├── mcp-server/                # MCP Server（npm 包）
│   │   ├── package.json
│   │   └── src/
│   ├── lsp-server/                # LSP Server（npm 包）
│   │   ├── package.json
│   │   └── src/
│   ├── cli/                       # CLI（独立二进制）
│   │   ├── pyproject.toml
│   │   └── src/
│   └── proxy/                     # API Proxy（Docker 镜像）
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── src/
├── dashboard/                     # Web Dashboard（Phase 4）
│   ├── backend/
│   └── frontend/
├── examples/                      # 集成示例
│   ├── killer-demo.py             # 5 分钟杀手级 Demo
│   ├── openclaw-integration.py
│   ├── langchain-integration.py
│   └── policy-examples/           # 实战策略模板
│       ├── production-db-safe.yaml
│       ├── enterprise-compliance.yaml
│       └── development-lenient.yaml
├── policies/                      # 内置策略模板
│   ├── default.yaml
│   ├── strict.yaml
│   ├── development.yaml
│   └── production.yaml
└── README.md
```

---

## 十六、开发阶段与里程碑

| 阶段 | 交付物 | 工时 | 关键验证 |
|:---|:---|:---|:---|
| **Phase 1** | Python SDK（Schema + Semantic 规则模式 + Policy）+ CLI + 测试 | 6h | openclaw 集成跑通 |
| **Phase 2** | Semantic 分类器/Embedding 模式 + 自动修正 + MCP Server | 4h | Cursor 里能拦截 DROP TABLE |
| **Phase 3** | LSP Server + API Proxy | 4h | VS Code 红色波浪线标注；零侵入接入 |
| **Phase 4** | Dashboard + 审计系统 + 文档 + 发布 | 5h | PyPI 发布，GitHub 开源 |
| **合计** | — | **19h 编码** | — |

> 加上代码审查、文档完善、发布流程，约 **25 小时 / 3-4 个工作日**（按 AI 生成速度）

---

## 附录 A：v1.0 → v2.0 变更记录

| 变更 | 说明 |
|:---|:---|
| 修复 GuardResult.finalize() bug | auto_fix 成功时 output 现在正确指向修正后内容 |
| 升级 Semantic Guard | 从简单余弦相似度 → 规则/分类器/Embedding/LLM-as-Judge 四层决策 |
| 规范 Policy DSL | 从字符串条件 → 结构化 condition 对象 + 运算符表 |
| 新增错误处理 | 统一异常体系 + 超时保护 + 降级链 |
| 新增安全考量 | 防注入、防 DoS、哈希链防篡改、数据隐私 |
| 新增配置管理 | 多级配置 + 热更新 + PolicyWatcher |
| 详化 MCP/LSP/Proxy | MCP Tools/Resources 完整定义；LSP Diagnostics/CodeAction；API Proxy 识别规则 |
| 新增审计系统 | 哈希链存储 + 多后端 + 防篡改验证 |
| 新增部署架构 | 开发/团队/企业三级部署方案 |
| 新增测试策略 | 分层测试 + 关键场景清单 |
| 新增性能优化 | 缓存策略 + 异步支持 + 批处理 |
| 新增统一异常 | GuardError / GuardTimeoutError / SchemaValidationError / PolicyLoadError |
