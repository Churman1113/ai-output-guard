# AgentGuard — 产品定义书 v2.0

> **定位**：AI 输出安全中间件 — 插在 LLM 和用户之间的安全带
>
> **v2.0 变更**：融入竞品分析洞察、新增风险分析/GTM/定价/社区策略、强化差异化叙事

---

## 一、问题定义

### 1.1 核心痛点

LLM（大语言模型）的输出不可靠，具体表现为三类问题：

| 问题类型 | 表现 | 后果 | 数据支撑（Pain Radar） |
|:---|:---|:---|:---|
| **结构错误** | JSON 字段缺失、类型不对、嵌套层级错误 | 下游解析崩溃，Agent 执行中断 | OutputParserException（26pts）、stale structured_response（25pts） |
| **语义漂移** | 幻觉 API、捏造参数、执行危险操作 | 生产事故、数据泄露、资金损失 | DeepSeek multi-turn 400 error（15pts）、agent config propagation failure（5pts） |
| **策略违规** | 绕过权限、访问未授权资源、不合规输出 | 安全审计失败、合规风险 | "How do you safely give LLMs SSH/DB access?"（85pts） |

### 1.2 现有方案的缺陷

| 方案 | 解决了什么 | 没解决什么 |
|:---|:---|:---|
| **instructor**（13k⭐） | 结构化输出 | 只管 Schema，不管语义和策略 |
| **guardrails-ai**（6.9k⭐） | 内容过滤 | 验证器扁平无层次，无策略引擎，RAIL 配置复杂 |
| **LangChain with_structured_output** | 框架内结构化 | 绑定 LangChain 生态，非通用 |
| **Outlines**（13.8k⭐） | 约束解码 100% 结构化 | 需控制推理过程，对闭源 API 不可用 |
| **NeMo Guardrails**（6.1k⭐） | 对话护栏 | 无 Schema 层，Colang DSL 复杂，偏对话场景 |
| **Authensor** | 策略引擎+MCP 安全 | 无 Schema/语义层，三层不递进 |
| **LlamaFirewall**（Meta） | Agent 安全护栏 | 偏检测层，无策略执行引擎和结构化校验 |
| **各 IDE 自带安全检查** | 基础防护 | 规则硬编码，不可扩展，无统一标准 |

**空白**：没有一个统一的、三层递进（结构 → 语义 → 策略）的 AI 输出安全引擎，也没有任何产品通过 LSP/MCP 深入 IDE 工作流。

### 1.3 Why Now — 为什么是 2026 年

| 趋势 | 影响 |
|:---|:---|
| **AI Agent 爆发**：AutoGen/CrewAI/openclaw/LangGraph 等框架 2024-2025 年用户增长 10x | Agent 自主执行能力提升，输出错误的爆炸半径同步放大 |
| **MCP 协议标准化**：Anthropic 主导的 MCP 协议被 Cursor/Copilot/Claude Code 等主流 IDE 采纳 | IDE 内集成安全校验的通道首次打通 |
| **LLM 输出可靠性成为瓶颈**：结构化输出从"锦上添花"变为"必需品" | instructor 13k⭐ 证明需求真实，但仅覆盖 Schema 层 |
| **监管压力**：EU AI Act 2025 生效、中国生成式 AI 管理办法落地 | 企业对 AI 输出合规的刚性需求出现 |
| **Authensor/LlamaFirewall 刚起步**：竞品尚未形成护城河 | 窗口期 6-12 个月，先发优势至关重要 |

---

## 二、产品定位

### 2.1 一句话定义

> AgentGuard 是一个 AI 输出安全引擎，以 Python SDK 为核心，通过 Schema / Semantic / Policy 三层递进校验拦截 LLM 的不可靠输出，并通过 SDK / MCP / LSP / CLI / API Proxy 五种协议形态分发，覆盖从开发者到普通用户到企业团队的全场景。

### 2.2 核心价值主张

```
LLM 输出 → [Schema Guard] → [Semantic Guard] → [Policy Guard] → 安全输出
              结构对吗？        意图安全吗？        合规吗？
              ↓ 不对            ↓ 危险             ↓ 违规
              自动修正           拦截+告警          拦截/需人工确认
```

三层递进，每一层解决一类问题，可独立使用也可组合使用。

### 2.3 与竞品的差异化（竞品分析升级版）

| 维度 | Instructor | Guardrails AI | NeMo Guardrails | Authensor | LlamaFirewall | **AgentGuard** |
|:---|:---|:---|:---|:---|:---|:---|
| Schema 校验 | ✅ Pydantic | ✅ RAIL | ❌ | ❌ | ❌ | ✅ Pydantic+JSONSchema |
| 语义校验 | ❌ | ⚠️ 验证器 | ⚠️ Colang | ⚠️ Aegis扫描 | ✅ 注入检测 | ✅ 分类器+规则混合 |
| 策略控制 | ❌ | ❌ | ⚠️ 对话控制 | ✅ 策略引擎 | ❌ | ✅ YAML DSL+规则引擎 |
| 三层递进 | ❌ | ❌ 扁平 | ❌ 扁平 | ❌ 独立模块 | ❌ | ✅ **渐进式流水线** |
| MCP 集成 | ❌ | ❌ | ❌ | ⚠️ 早期 | ❌ | ✅ |
| LSP 集成 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ **蓝海** |
| CLI | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| API Proxy | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 零侵入 |
| 适配所有 LLM | ❌ 依赖FC | ✅ | ✅ | ✅ | ❌ 需部署 | ✅ |
| 审计日志 | ❌ | ❌ | ❌ | ✅ 哈希链 | ❌ | ✅ |
| 自动修正 | ⚠️ 重试 | ❌ | ❌ | ❌ | ❌ | ✅ |

**不可替代性叙事**：
- **LSP 形态是蓝海**：没有任何竞品在编辑器中实时标注 AI 输出安全问题。开发者熟悉的 Linter 体验 + AI 安全 = 独特品类
- **三层递进是架构壁垒**：Authensor 有三层但是独立模块，NeMo 有五种护栏但是扁平编排。AgentGuard 的"流水线递进"（前一层通过才进入下一层）是有意为之——结构错了就别谈语义，语义危险了就别查策略
- **五形态分发是渠道壁垒**：一个核心引擎 → 五个分发通道，竞品只覆盖 1-2 个

---

## 三、目标用户

### 3.1 三类用户画像

| 用户类型 | 身份 | 核心需求 | 痛点频率 | 接入方式 |
|:---|:---|:---|:---|:---|
| **Agent 开发者** | 写 Python 代码构建 AI Agent 的人 | 在代码里校验 LLM 输出，防止 Agent 执行异常 | 每次调用都可能出错 | Python SDK |
| **AI 工具用户** | 用 Cursor/Copilot/灵码等工具但不写 Guard 代码的人 | IDE 里自动拦截 AI 的危险建议 | 偶尔遇到但后果严重 | MCP/LSP 插件 |
| **团队/企业** | 管理一组人的 AI 使用安全的管理员 | 统一策略、审计合规、零侵入部署 | 合规刚需 | API Proxy + Dashboard |

### 3.2 用户旅程

**Agent 开发者**（5 分钟上手）：
```
pip install agentguard
→ 定义 Schema + Policy
→ guard.validate(output)
→ 拿到 GuardResult（含拦截原因 + 修正建议）
```

**AI 工具用户**（1 分钟上手）：
```
IDE 设置里加 MCP 配置（一行 JSON）
→ 重启 IDE
→ AI 输出自动经过 Guard
→ 危险操作被拦截并提示（LSP Diagnostics 红色波浪线）
```

**团队管理员**（10 分钟部署）：
```
docker run agentguard/proxy
→ 团队成员设 HTTP_PROXY
→ 所有 AI 请求自动过 Guard
→ Dashboard 看审计日志 + 拦截统计
```

### 3.3 典型场景详述

**场景 1：Agent 执行数据库操作**
```
LLM 输出: {"action": "execute_sql", "query": "DROP TABLE users"}
                                          ↓
Schema Guard: ✅ 结构正确（action + query 字段都有）
Semantic Guard: 🔴 匹配到 "drop_table" 危险意图（相似度 0.92）
Policy Guard: （未执行，被 Semantic 层拦截）
结果: DENY — "语义匹配到危险意图: drop_table"
```

**场景 2：LLM 拼写错误的自动修正**
```
LLM 输出: {"endpoint": "/api/users", "method": "DELTE", "params": {}}
                                                    ↓
Schema Guard: ⚠️ method 枚举值错误，自动修正 "DELTE" → "DELETE"
Semantic Guard: ✅ DELETE /api/users 语义正常
Policy Guard: ✅ /api/* 非生产环境，自动放行
结果: FIX — 自动修正后通过
```

**场景 3：策略要求人工确认**
```
LLM 输出: {"action": "deploy", "target": "production", "version": "3.2.1"}
                                                          ↓
Schema Guard: ✅
Semantic Guard: ✅
Policy Guard: ⚠️ 命中规则 "生产部署需人工确认"
结果: ASK_HUMAN — "正在部署到生产环境，是否继续？"
```

---

## 四、核心功能

### 4.1 Schema Guard（结构守卫）

**做什么**：校验 LLM 输出是否符合预期的数据结构。

**技术方案**：
- 输入：pydantic Model 或 JSON Schema
- 校验：字段存在性、类型匹配、嵌套层级、枚举值、必填项
- 输出：通过 / 修正建议 + 自动修复尝试
- 自动修正策略：
  1. **枚举模糊匹配**：`"DELTE"` → Levenshtein 距离 → `"DELETE"`
  2. **类型强转**：`"123"` → `123`，`"true"` → `True`
  3. **默认值填充**：缺失可选字段 → 填充默认值
  4. **多余字段剥离**：未知字段 → 移除（严格模式）/ 保留（宽容模式）
  5. **嵌套修复**：递归应用以上策略到子对象

**修正可信度**：每个修正操作附带 confidence 分数，低置信度修正标记为 WARN 而非 FIX。

```python
from agentguard import Guard
from pydantic import BaseModel

class APIResponse(BaseModel):
    endpoint: str
    method: str  # GET/POST/PUT/DELETE
    params: dict

guard = Guard(schema=APIResponse)
result = guard.validate('{"endpoint": "/users", "method": "DELTE", "params": {}}')
# → FIX: method 枚举值自动修正为 "DELETE" (confidence: 0.95)
```

### 4.2 Semantic Guard（语义守卫）

**做什么**：校验 LLM 输出的语义是否安全、合理、符合预期意图。

**技术方案**（v2.0 升级：从简单余弦相似度 → 分类器 + 规则混合）：

| 方案 | 适用场景 | 延迟 | 准确率 |
|:---|:---|:---|:---|
| **规则模式**（关键词+正则+启发式） | 确定性高危模式（DROP TABLE, rm -rf） | <1ms | 99%+ |
| **轻量分类器**（FastText/小模型） | 意图分类（删除/修改/发送/访问） | <10ms | 90%+ |
| **Embedding 相似度**（sentence-transformers） | 语义漂移检测、低置信度边界判断 | <50ms | 85%+ |
| **LLM-as-Judge**（可选，调用 LLM 评判） | 复杂场景、边界案例 | <2s | 95%+ |

**分层决策**：
```
规则模式（确定性拦截） → 轻量分类器（快速分类） → Embedding（语义判别） → LLM-as-Judge（可选兜底）
         ↓ 命中                ↓ 高置信度            ↓ 高置信度            ↓ 人工确认
       DENY                 DENY/WARN            DENY/WARN           ASK_HUMAN
```

**内置危险意图分类体系**（5 大类 20+ 子类）：

| 大类 | 子类示例 | 拦截级别 |
|:---|:---|:---|
| **数据破坏** | drop_table, delete_all, truncate, rm_recursive | DENY |
| **系统操作** | execute_shell, ssh_connect, sudo, modify_system | DENY/WARN |
| **网络风险** | send_email, external_request, data_exfiltration | WARN |
| **凭据泄露** | access_secret, expose_api_key, read_credentials | DENY |
| **合规风险** | pii_exposure, bias_output, hallucinated_api | WARN |

```python
guard = Guard(
    schema=APIResponse,
    semantic=True,
    dangerous_intents=["drop_table", "delete_all", "send_email", "ssh_connect"]
)
result = guard.validate('{"endpoint": "/db", "method": "POST", "params": {"query": "DROP TABLE users"}}')
# → DENY: 语义匹配到 drop_table 危险意图（规则模式命中，置信度 1.0）
```

### 4.3 Policy Guard（策略守卫）

**做什么**：基于规则 DSL 执行访问控制、合规检查、审计记录。

**策略 DSL 语法规范**：
```yaml
# policy.yaml — 策略定义文件
version: "1.0"

defaults:
  on_no_match: allow    # 无规则命中时的默认动作
  on_error: pass        # Guard 本身出错时的降级策略

rules:
  - name: "禁止访问生产数据库"
    priority: 100                    # 优先级，数字越大越先匹配
    condition:
      all:                           # 逻辑组合：all(AND) / any(OR)
        - field: "output.endpoint"
          operator: "matches"        # matches/equals/contains/startswith/in/gt/lt
          value: "/prod/*"
    action: deny
    message: "策略禁止访问生产环境"
    audit: true                      # 记录审计日志

  - name: "敏感操作需人工确认"
    priority: 90
    condition:
      all:
        - field: "output.method"
          operator: "equals"
          value: "DELETE"
        - field: "output.params.scope"
          operator: "equals"
          value: "all"
    action: ask_human
    message: "正在执行批量删除，是否继续？"
    timeout: 300                     # 人工确认超时（秒），超时后执行 fallback
    fallback: deny                   # 超时后的降级动作

  - name: "开发环境自动放行"
    priority: 50
    condition:
      any:
        - field: "output.endpoint"
          operator: "startswith"
          value: "/dev/"
        - field: "output.endpoint"
          operator: "startswith"
          value: "/staging/"
    action: allow
    audit: false
```

**运算符完整列表**：

| 运算符 | 含义 | 示例 |
|:---|:---|:---|
| `equals` | 精确匹配 | `field: "method", value: "DELETE"` |
| `not_equals` | 不等于 | — |
| `contains` | 包含子串 | `field: "query", value: "DROP"` |
| `matches` | 正则匹配 | `field: "endpoint", value: "/prod/*"` |
| `startswith` | 前缀匹配 | `field: "endpoint", value: "/dev/"` |
| `endswith` | 后缀匹配 | — |
| `in` | 属于集合 | `field: "method", value: ["DELETE", "PUT"]` |
| `gt` / `gte` | 大于 / 大于等于 | `field: "params.limit", value: 1000` |
| `lt` / `lte` | 小于 / 小于等于 | — |
| `exists` | 字段存在 | `field: "params.admin"` |
| `not_exists` | 字段不存在 | — |

### 4.4 三层组合使用

```python
from agentguard import Guard, GuardLevel
from pydantic import BaseModel

class AgentAction(BaseModel):
    action: str
    target: str
    params: dict = {}

guard = Guard(
    schema=AgentAction,                    # Schema Guard
    semantic=True,                          # Semantic Guard
    dangerous_intents=["drop_table", "execute_shell"],
    policy="policies/production.yaml",      # Policy Guard
    on_fail="deny",                         # 失败时拒绝
    auto_fix=True,                          # 自动修正
)

# 场景 1：全部通过
result = guard.validate('{"action": "query", "target": "/api/users", "params": {}}')
# → GuardLevel.PASS, output = 原始输出

# 场景 2：Schema 修正后通过
result = guard.validate('{"action": "qery", "target": "/api/users", "param": {}}')
# → GuardLevel.FIX, output = 修正后输出, checks[0].fix = "..."

# 场景 3：语义拦截
result = guard.validate('{"action": "execute", "target": "/db", "params": {"query": "DROP TABLE users"}}')
# → GuardLevel.DENY, blocked_by = "semantic"

# 场景 4：策略要求人工确认
result = guard.validate('{"action": "deploy", "target": "/prod/app", "params": {"version": "3.2.1"}}')
# → GuardLevel.ASK_HUMAN, checks[2].message = "生产部署需人工确认"
```

---

## 五、分发形态

### 5.1 五种协议层

| 协议层 | 分发物 | 覆盖范围 | 用户动作 | 上手时间 |
|:---|:---|:---|:---|:---|
| **Python SDK** | pip 包 | 任何 Python 代码 | `pip install agentguard` | 5 min |
| **MCP Server** | npm 包 | Cursor、Claude Code、Copilot、Windsurf、通义灵码、豆包 MarsCode、Cline | 加一行 MCP 配置 | 1 min |
| **LSP Server** | npm 包 | VS Code、JetBrains、Vim/Neovim、Emacs、Zed、Sublime、DevEco Studio、Eclipse | 装语言服务器插件 | 3 min |
| **CLI** | 独立二进制 | 终端、Git Hooks、CI/CD、百度 Comate | `agentguard check "内容"` | 即时 |
| **API Proxy** | Docker 镜像 | **所有** AI 工具（零改动） | 设 `HTTP_PROXY` 环境变量 | 10 min |

### 5.2 协议层优先级与开发顺序

```
Phase 1: Python SDK（核心引擎）→ CLI（调试+CI/CD）
Phase 2: MCP Server（IDE 生态，覆盖 Cursor 等主流 AI IDE）
Phase 3: LSP Server（编辑器原生体验，蓝海差异化）
Phase 4: API Proxy（零侵入企业场景）→ Dashboard
```

Python SDK 是一切的基础，其他协议层是 SDK 的包装和分发通道。

### 5.3 各形态的核心价值

| 形态 | 解决的核心问题 | 竞品空白 |
|:---|:---|:---|
| Python SDK | Agent 开发者缺统一的输出校验工具 | instructor 只管 Schema |
| MCP Server | AI IDE 用户无法自定义安全规则 | 无竞品做 MCP 安全 |
| LSP Server | 编辑器里没有 AI 输出安全标注 | **完全蓝海** |
| CLI | CI/CD 流水线缺 AI 输出门禁 | 无竞品 |
| API Proxy | 企业想零代码接入 AI 安全 | Bifrost 做了网关但无自有引擎 |

---

## 六、风险分析

### 6.1 竞争风险

| 竞品 | 威胁等级 | 风险描述 | 应对策略 |
|:---|:---|:---|:---|
| **Authensor** | 🔴 高 | 架构理念最接近（三层+MCP+策略引擎+审计），直接竞品 | 加速 MVP 发布抢占心智；强调三层**递进**而非独立模块；在 Authensor 薄弱的 Schema/语义层建立壁垒 |
| **LlamaFirewall** | 🔴 高 | Meta 品牌+Agent 定位，可能快速获得开发者关注 | 差异化定位：LlamaFirewall 偏检测，AgentGuard 做执行（不只是发现，还要拦截/修正）；LSP 形态 Meta 短期不会做 |
| **NeMo Guardrails** | 🟡 中 | NVIDIA 生态背书，企业客户基础 | AgentGuard 更轻量、更开发者友好；NeMo 偏对话场景，AgentGuard 专注 Agent 输出 |
| **Instructor** | 🟡 中 | 13k⭐ 用户基础，Schema 层心智占领 | 不在 Schema 层竞争——Instructor 是"提取工具"，AgentGuard 是"安全引擎"，可共存甚至集成 |
| **Guardrails AI** | 🟢 低 | 验证器生态成熟但架构老旧，增长放缓 | 三层递进架构天然优于扁平验证器；Hub 生态可被 AgentGuard 插件系统超越 |

### 6.2 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|:---|:---|:---|:---|
| Semantic Guard 误报率过高 | 中 | 用户体验差，放弃使用 | 规则模式兜底（零误报）；分级决策（高置信度才拦截）；可配置阈值+白名单 |
| Embedding 模型体积大、加载慢 | 中 | 安装体验差 | 默认用规则+轻量分类器模式；Embedding 模型可选安装（`pip install agentguard[semantic]`） |
| API Proxy 拦截导致 LLM 请求失败 | 低 | 生产事故 | Fail-open 降级策略；请求转发超时兜底；完整的错误处理+重试 |
| LSP Server 与多 IDE 兼容性问题 | 中 | 覆盖面受限 | 先做 VS Code（最大用户群）→ JetBrains → 其他；LSP 协议标准化降低适配成本 |
| Policy DSL 功能膨胀 | 低 | 配置复杂，偏离"简洁"初衷 | 保持 YAML 声明式；限制运算符数量；复杂场景推荐用 Python SDK 自定义 |

### 6.3 市场风险

| 风险 | 概率 | 影响 | 缓解措施 |
|:---|:---|:---|:---|
| AI 安全需求不够刚性，Nice-to-have 而非 Must-have | 中 | 增长缓慢 | 瞄准 Agent 场景（输出错误 = 生产事故，更刚性）；打造"5 分钟 demo 拦截 DROP TABLE"的震撼体验 |
| 开源社区增长不及预期 | 中 | 影响力不足 | 主动集成到热门框架（LangChain/AutoGen/CrewAI）；高质量文档+示例；开发者关系运营 |
| LLM 提供商内置安全能力取代第三方 | 低 | 核心价值被侵蚀 | LLM 内置安全是通用化的，无法满足企业定制策略；多层 Guard 的组合价值不可替代 |

---

## 七、Go-to-Market 策略

### 7.1 Phase 1：种子期（Month 1-2）

**目标**：500 GitHub Stars，100 周活跃用户

| 动作 | 渠道 | 预期效果 |
|:---|:---|:---|
| 发布 Python SDK + CLI | GitHub + PyPI | 核心开发者可用 |
| "5 分钟拦截 DROP TABLE" Demo 视频 | Twitter/X + Reddit r/LocalLLaMA + Hacker News | 病毒式传播 |
| 集成教程：LangChain + AutoGen + CrewAI | GitHub README + Dev.to + Medium | SEO + 框架用户转化 |
| Authensor 对比文档 | GitHub Wiki | 技术决策者对比参考 |

### 7.2 Phase 2：增长期（Month 3-4）

**目标**：2,000 Stars，500 周活跃用户

| 动作 | 渠道 | 预期效果 |
|:---|:---|:---|
| 发布 MCP Server | GitHub + npm | Cursor/Copilot 用户零门槛接入 |
| "LSP 安全校验" Demo — 编辑器红色波浪线标注 AI 危险输出 | Twitter/X + YouTube | 蓝海差异化引爆 |
| 开源贡献者计划 | GitHub Discussions | 社区贡献策略模板/意图库 |
| Agent 框架官方集成 PR | LangChain/AutoGen/CrewAI GitHub | 框架级分发 |

### 7.3 Phase 3：商业化（Month 5-6）

**目标**：10 付费团队，$500 MRR

| 动作 | 渠道 | 预期效果 |
|:---|:---|:---|
| 发布 API Proxy + Dashboard | Docker Hub + 官网 | 企业零侵入部署 |
| 团队版定价上线 | 官网 | MRR 起步 |
| 企业案例研究 | Blog + 社交媒体 | 社会信任 |
| YC/安全赛道加速器申请 | YC/Techstars | 品牌+资金+网络 |

### 7.4 核心增长飞轮

```
开发者试用 SDK → 觉得有用 → 分享到社交媒体/技术论坛
       ↓
框架集成 PR 被合并 → 框架用户自动发现 AgentGuard
       ↓
IDE 插件安装 → 团队其他成员看到 → 团队采纳
       ↓
团队版 Dashboard → 企业采购 → 口碑传播
```

---

## 八、定价与商业模式

### 8.1 定价策略（Open Core）

| 层级 | 价格 | 包含内容 | 目标用户 |
|:---|:---|:---|:---|
| **Community** | 免费 | Python SDK + CLI + MCP Server + LSP Server + 基础策略模板 | 个人开发者 |
| **Team** | $29/月/团队 | + API Proxy + Dashboard + 团队策略管理 + 审计日志导出 | 小团队 |
| **Enterprise** | 咨询定价 | + SSO/SAML + 自定义部署 + SLA + 优先支持 + 合规报告 | 中大型企业 |

### 8.2 商业化路径

```
Month 1-2: 完全免费，积累用户和社区
Month 3-4: 发布 API Proxy + Dashboard Preview，开始 Team 版 waitlist
Month 5-6: Team 版正式上线，第一批付费用户
Month 7+: Enterprise 功能迭代（SSO、合规报告、自定义部署）
```

### 8.3 开源治理

| 项目 | 策略 |
|:---|:---|
| 核心引擎（agentguard） | MIT License — 最大化采用率 |
| 策略模板库 | MIT License — 社区贡献 |
| Dashboard | BSL 1.1（3年后转MIT）— 保护商业化 |
| 内置意图库 | CC-BY-SA — 社区共建 |

**CLA 策略**：采用 Apache CLA，贡献者保留版权但授予项目宽松使用许可。

---

## 九、非功能性需求

### 9.1 性能

| 指标 | 目标 | 说明 |
|:---|:---|:---|
| Schema Guard 延迟 | < 1ms | 纯内存校验 |
| Semantic Guard（规则模式） | < 1ms | 关键词/正则匹配 |
| Semantic Guard（分类器模式） | < 10ms | FastText 轻量推理 |
| Semantic Guard（Embedding 模式） | < 50ms | 本地模型（可选安装） |
| Policy Guard 延迟 | < 5ms | 规则引擎匹配 |
| 三层全开（规则+分类器模式） | < 20ms | 用户无感 |
| 三层全开（含 Embedding） | < 60ms | 可接受 |
| API Proxy 吞吐 | > 1000 req/s | 不成为瓶颈 |
| API Proxy 额外延迟 | < 10ms | 请求转发开销 |

### 9.2 可靠性

- **Fail-Open 策略**：Guard 本身不可成为单点故障——校验出错时默认放行 + 告警（可配置为 Fail-Closed）
- **降级策略**：Semantic Guard 的 Embedding 模型加载失败 → 自动降级到规则+分类器模式
- **超时控制**：每层校验有独立超时（Schema: 100ms, Semantic: 500ms, Policy: 200ms），超时按 on_error 配置处理
- 所有异常捕获并记录，不抛出未处理异常

### 9.3 可扩展性

- 自定义校验器（继承 BaseGuard）
- 自定义意图分类器（实现 IntentClassifier 协议）
- 自定义策略动作（实现 ActionHandler 协议）
- 插件系统（entry_points 注册，`pip install agentguard-plugin-xxx`）

### 9.4 安全性

- Guard 自身防注入：策略文件 YAML 解析启用 safe_load，禁止任意代码执行
- 审计日志防篡改：日志条目含哈希链（借鉴 Authensor）
- API Proxy 的 TLS 终止由用户控制，Proxy 不解密 TLS
- 敏感数据不落盘：默认内存模式，审计日志可选加密存储

---

## 十、命名与品牌

| 项目 | 值 |
|:---|:---|
| **产品名** | AgentGuard |
| **包名** | `agentguard` |
| **Slogan** | The seatbelt between LLMs and your systems |
| **Logo 概念** | 盾牌 + 代码符号，主色调蓝/绿（安全 + 可靠） |
| **域名** | agentguard.dev（待注册） |
| **社交账号** | @AgentGuardDev（Twitter/X） |

---

## 十一、成功指标

### 11.1 MVP 阶段（Month 1-2）

| 指标 | 目标 | 衡量方式 |
|:---|:---|:---|
| GitHub Stars | 500+ | GitHub API |
| pip 周下载量 | 1,000+ | PyPI stats |
| Demo 视频播放量 | 10,000+ | YouTube/Twitter |
| 集成的 Agent 框架 | 2+（LangChain + AutoGen） | PR 合并 |
| Bug 报告响应时间 | < 24h | GitHub Issues |

### 11.2 增长阶段（Month 3-6）

| 指标 | 目标 | 衡量方式 |
|:---|:---|:---|
| GitHub Stars | 2,000+ | GitHub API |
| pip 周下载量 | 5,000+ | PyPI stats |
| MCP Server 安装量 | 1,000+ | npm downloads |
| IDE 插件安装量 | 500+ | Marketplace 统计 |
| 社区贡献的策略模板 | 20+ | GitHub PR |
| 集成的 Agent 框架 | 5+ | PR 合并 |

### 11.3 商业化阶段（Month 6+）

| 指标 | 目标 | 衡量方式 |
|:---|:---|:---|
| 付费团队数 | 10+ | Stripe |
| MRR | $500+ | Stripe |
| 企业 POC | 5+ | 销售 pipeline |
| Net Promoter Score | > 40 | 用户调查 |

---

## 附录 A：竞品威胁矩阵

```
                    功能重叠度 →
                    低           中           高
              ┌────────────┬────────────┬────────────┐
        高    │ LlamaFirewall│ NeMo       │ Authensor  │ ← 最危险
  品牌影      │ (Meta)      │ (NVIDIA)   │            │
  响力 ↓      ├────────────┼────────────┼────────────┤
        中    │ Guardrails AI│ Instructor │ Bifrost    │
              │             │            │            │
              ├────────────┼────────────┼────────────┤
        低    │ Nudge Sec.  │ Marvin     │ DSPy       │
              │             │            │            │
              └────────────┴────────────┴────────────┘
```

**关键洞察**：Authensor 是最危险竞品（高重叠+技术接近），但品牌影响力低，AgentGuard 有先发窗口。LlamaFirewall 品牌最强但功能重叠度有限（偏检测，无策略执行）。建议 AgentGuard 主打"三层递进+LSP蓝海"叙事，避免与 Authensor 正面比拼策略引擎。
