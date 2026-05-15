# AgentGuard — 实战策略模板 v1.0

> 开箱即用的策略模板，覆盖最常见的 AI 输出安全场景。
> 每个模板含完整注释，可直接复制使用或组合修改。

---

## 一、数据库操作安全（production-db-safe.yaml）

```yaml
# ──────────────────────────────────────────────
# 场景：Agent 可以查询数据库，但不能执行危险操作
# 适用：所有连接数据库的 AI Agent
# ──────────────────────────────────────────────
version: "1.0"

defaults:
  on_no_match: allow
  on_error: pass

rules:
  # ── 硬拦截：绝对禁止 ──

  - name: "禁止 DROP/TRUNCATE 操作"
    priority: 200
    condition:
      any:
        - field: "output.query"
          operator: "matches"
          value: "(?i)\\b(DROP|TRUNCATE)\\b"
        - field: "output.action"
          operator: "in"
          value: ["drop_table", "truncate_table"]
    action: deny
    message: "安全策略禁止执行 DROP/TRUNCATE 操作"
    audit: true

  - name: "禁止无 WHERE 的 DELETE/UPDATE"
    priority: 190
    condition:
      all:
        - field: "output.action"
          operator: "in"
          value: ["execute_sql", "run_query"]
        - field: "output.query"
          operator: "matches"
          value: "(?i)\\b(DELETE|UPDATE)\\b(?!.*\\bWHERE\\b)"
    action: deny
    message: "禁止无 WHERE 条件的 DELETE/UPDATE 操作"
    audit: true

  - name: "禁止修改系统表"
    priority: 180
    condition:
      all:
        - field: "output.action"
          operator: "in"
          value: ["execute_sql", "run_query"]
        - field: "output.query"
          operator: "matches"
          value: "(?i)\\b(pg_|information_schema|mysql|sys)\\."
    action: deny
    message: "禁止操作系统表"
    audit: true

  # ── 人工确认：高风险但可能合理 ──

  - name: "批量操作需确认"
    priority: 150
    condition:
      all:
        - field: "output.action"
          operator: "in"
          value: ["execute_sql", "run_query"]
        - field: "output.query"
          operator: "matches"
          value: "(?i)\\b(DELETE|UPDATE)\\b.*\\bWHERE\\b"
    action: ask_human
    message: "即将执行 DELETE/UPDATE 操作，请确认 SQL 语句正确"
    timeout: 120
    fallback: deny
    audit: true

  - name: "ALTER TABLE 需确认"
    priority: 140
    condition:
      all:
        - field: "output.action"
          operator: "in"
          value: ["execute_sql", "run_query"]
        - field: "output.query"
          operator: "matches"
          value: "(?i)\\bALTER\\s+TABLE\\b"
    action: ask_human
    message: "ALTER TABLE 操作会修改表结构，请确认"
    timeout: 300
    fallback: deny
    audit: true

  # ── 自动放行：低风险操作 ──

  - name: "SELECT 查询自动放行"
    priority: 50
    condition:
      all:
        - field: "output.action"
          operator: "in"
          value: ["execute_sql", "run_query", "read_data"]
        - field: "output.query"
          operator: "matches"
          value: "(?i)^\\s*SELECT\\b"
    action: allow
    audit: false
```

---

## 二、API 调用防护（api-call-safe.yaml）

```yaml
# ──────────────────────────────────────────────
# 场景：Agent 通过 HTTP API 与外部服务交互
# 适用：所有调用 REST API 的 AI Agent
# ──────────────────────────────────────────────
version: "1.0"

defaults:
  on_no_match: allow
  on_error: pass

rules:
  # ── 硬拦截 ──

  - name: "禁止访问内部 API"
    priority: 200
    condition:
      any:
        - field: "output.endpoint"
          operator: "matches"
          value: "(?i)https?://(10\\.|172\\.(1[6-9]|2\\d|3[01])\\.|192\\.168\\.)"
        - field: "output.endpoint"
          operator: "matches"
          value: "(?i)https?://.*\\.internal\\."
        - field: "output.endpoint"
          operator: "matches"
          value: "(?i)https?://localhost"
    action: deny
    message: "禁止访问内部网络 API"
    audit: true

  - name: "禁止凭证泄露"
    priority: 190
    condition:
      any:
        - field: "output.headers.Authorization"
          operator: "exists"
        - field: "output.params.api_key"
          operator: "exists"
        - field: "output.params.token"
          operator: "exists"
    action: deny
    message: "禁止在请求中包含认证凭证"
    audit: true

  - name: "禁止 DELETE 方法调用外部 API"
    priority: 180
    condition:
      all:
        - field: "output.method"
          operator: "equals"
          value: "DELETE"
        - field: "output.endpoint"
          operator: "matches"
          value: "(?i)https?://"
    action: deny
    message: "禁止使用 DELETE 方法调用外部 API"
    audit: true

  # ── 人工确认 ──

  - name: "POST/PUT 到外部服务需确认"
    priority: 100
    condition:
      all:
        - field: "output.method"
          operator: "in"
          value: ["POST", "PUT", "PATCH"]
        - field: "output.endpoint"
          operator: "matches"
          value: "(?i)https?://"
    action: ask_human
    message: "即将向外部服务发送写入请求，请确认"
    timeout: 60
    fallback: deny
    audit: true

  # ── 白名单放行 ──

  - name: "白名单 API 自动放行"
    priority: 50
    condition:
      any:
        - field: "output.endpoint"
          operator: "startswith"
          value: "https://api.weather.com/"
        - field: "output.endpoint"
          operator: "startswith"
          value: "https://api.github.com/"
        - field: "output.endpoint"
          operator: "startswith"
          value: "https://search.example.com/"
    action: allow
    audit: false
```

---

## 三、CI/CD 门禁（ci-cd-gate.yaml）

```yaml
# ──────────────────────────────────────────────
# 场景：AI 生成的代码/配置在 CI/CD 中需经过安全审查
# 适用：GitHub Actions / GitLab CI 中的 agentguard check
# ──────────────────────────────────────────────
version: "1.0"

defaults:
  on_no_match: allow        # 未知内容默认放行（CI 不应阻断正常流程）
  on_error: pass            # Guard 出错时放行（不阻塞 CI）

rules:
  - name: "禁止硬编码密钥"
    priority: 200
    condition:
      any:
        - field: "output.raw"
          operator: "matches"
          value: "(?i)(password|secret|api_key|token)\\s*[:=]\\s*['\"][^'\"]{8,}['\"]"
        - field: "output.raw"
          operator: "matches"
          value: "(?i)AKIA[0-9A-Z]{16}"       # AWS Access Key
        - field: "output.raw"
          operator: "matches"
          value: "(?i)sk-[a-zA-Z0-9]{20,}"     # OpenAI API Key
    action: deny
    message: "检测到硬编码密钥/凭证，请使用环境变量"
    audit: true

  - name: "禁止危险 Docker 指令"
    priority: 180
    condition:
      any:
        - field: "output.raw"
          operator: "matches"
          value: "(?i)docker\\s+run.*--privileged"
        - field: "output.raw"
          operator: "matches"
          value: "(?i)docker\\s+run.*-v\\s+/:"
        - field: "output.raw"
          operator: "matches"
          value: "(?i)docker\\s+run.*--network\\s+host"
    action: deny
    message: "检测到危险的 Docker 运行参数"
    audit: true

  - name: "禁止写入敏感路径"
    priority: 170
    condition:
      any:
        - field: "output.raw"
          operator: "matches"
          value: "(?i)/(etc/passwd|etc/shadow|etc/hosts)\\b"
        - field: "output.raw"
          operator: "matches"
          value: "(?i)/var/log/\\w+\\s*$"        # 直接写日志文件
    action: deny
    message: "检测到写入系统敏感路径"
    audit: true

  - name: "sudo 操作需确认"
    priority: 100
    condition:
      field: "output.raw"
      operator: "matches"
      value: "(?i)\\bsudo\\b"
    action: ask_human
    message: "检测到 sudo 操作，请确认是否必要"
    timeout: 300
    fallback: deny
    audit: true
```

---

## 四、企业合规（enterprise-compliance.yaml）

```yaml
# ──────────────────────────────────────────────
# 场景：企业级 AI 使用合规管控
# 适用：金融/医疗/政府等高监管行业
# ──────────────────────────────────────────────
version: "1.0"

defaults:
  on_no_match: deny           # 默认拦截！未知内容不放行（白名单模式）
  on_error: deny              # Guard 出错也拦截（Fail-Closed）

rules:
  # ── 数据外泄防护 ──

  - name: "禁止 PII 数据输出"
    priority: 200
    condition:
      any:
        - field: "output.raw"
          operator: "matches"
          value: "(?i)\\b\\d{3}[-.]?\\d{2}[-.]?\\d{4}\\b"        # SSN
        - field: "output.raw"
          operator: "matches"
          value: "(?i)\\b[A-Z]{2}\\d{6}\\b"                       # Passport
        - field: "output.raw"
          operator: "matches"
          value: "(?i)\\b\\d{17}[\\dXx]\\b"                       # 中国身份证
        - field: "output.raw"
          operator: "matches"
          value: "(?i)[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}"  # Email
    action: deny
    message: "输出包含个人身份信息(PII)，已拦截"
    audit: true

  - name: "禁止敏感数据输出"
    priority: 190
    condition:
      any:
        - field: "output.raw"
          operator: "matches"
          value: "(?i)(银行卡|信用卡|bank\\s*card|credit\\s*card).{0,20}\\d{4}"
        - field: "output.raw"
          operator: "matches"
          value: "(?i)(工资|薪酬|salary|compensation).{0,20}\\d+"
    action: deny
    message: "输出包含敏感数据，已拦截"
    audit: true

  # ── 白名单放行 ──

  - name: "允许查询公开数据"
    priority: 50
    condition:
      all:
        - field: "output.action"
          operator: "equals"
          value: "query"
        - field: "output.datasource"
          operator: "equals"
          value: "public"
    action: allow
    audit: true

  - name: "允许生成报告（脱敏数据）"
    priority: 40
    condition:
      all:
        - field: "output.action"
          operator: "equals"
          value: "generate_report"
        - field: "output.sanitized"
          operator: "equals"
          value: "true"
    action: allow
    audit: true
```

---

## 五、开发环境宽松模式（development-lenient.yaml）

```yaml
# ──────────────────────────────────────────────
# 场景：开发环境，尽量少拦截，主要起记录作用
# 适用：本地开发、测试环境
# ──────────────────────────────────────────────
version: "1.0"

defaults:
  on_no_match: allow
  on_error: pass

rules:
  # 开发环境只拦截最危险的操作，其他都 warn

  - name: "仅拦截 DROP TABLE"
    priority: 200
    condition:
      field: "output.query"
      operator: "matches"
      value: "(?i)\\bDROP\\s+TABLE\\b"
    action: deny
    message: "即使在开发环境也不建议 DROP TABLE，请使用 DELETE 或 TRUNCATE"
    audit: true

  - name: "危险操作记录但不拦截"
    priority: 100
    condition:
      any:
        - field: "output.method"
          operator: "equals"
          value: "DELETE"
        - field: "output.action"
          operator: "equals"
          value: "execute_shell"
    action: allow            # 放行
    audit: true              # 但记录审计日志
```

---

## 六、策略组合指南

### 6.1 多策略文件合并

```python
# 方式 1：代码中指定
guard = Guard(
    schema=AgentAction,
    semantic=True,
    policy="policies/production-db-safe.yaml",  # 单个策略文件
)

# 方式 2：合并多个策略文件为一个大文件
# 使用 Python 合并：
import yaml

def merge_policies(*paths):
    merged = {"version": "1.0", "defaults": {}, "rules": []}
    for path in paths:
        with open(path) as f:
            policy = yaml.safe_load(f)
        if "defaults" in policy:
            merged["defaults"].update(policy["defaults"])
        merged["rules"].extend(policy.get("rules", []))
    # 按优先级排序
    merged["rules"].sort(key=lambda r: r.get("priority", 0), reverse=True)
    return merged
```

### 6.2 环境感知策略

```python
import os

env = os.getenv("ENVIRONMENT", "development")

policy_map = {
    "development": "policies/development-lenient.yaml",
    "staging": "policies/production-db-safe.yaml",
    "production": "policies/enterprise-compliance.yaml",
}

guard = Guard(
    schema=AgentAction,
    semantic=True,
    policy=policy_map.get(env, "policies/development-lenient.yaml"),
)
```

### 6.3 策略测试

```python
# 在 CI 中测试策略是否按预期工作
from agentguard import Guard, GuardLevel

def test_policy_blocks_drop_table():
    guard = Guard(schema=AgentAction, policy="policies/production-db-safe.yaml")
    result = guard.validate('{"action": "execute_sql", "query": "DROP TABLE users"}')
    assert result.level == GuardLevel.DENY
    assert result.blocked_by == "semantic"  # 规则模式先命中

def test_policy_allows_select():
    guard = Guard(schema=AgentAction, policy="policies/production-db-safe.yaml")
    result = guard.validate('{"action": "execute_sql", "query": "SELECT * FROM users"}')
    assert result.is_safe
```
