# AI Output Guard — 协议交互流程 v1.0

> MCP / LSP / API Proxy 三种协议的精确消息序列、请求/响应示例与生命周期管理。

---

## 一、MCP Server 协议流程

### 1.1 连接生命周期

```
IDE (Cursor/Claude Code)                    AI Output Guard MCP Server
        │                                            │
        │──── initialize ────────────────────────────▶│  握手
        │◀─── initialize response ──────────────────│
        │                                            │
        │──── tools/list ───────────────────────────▶│  发现工具
        │◀─── tools/list response ──────────────────│
        │                                            │
        │──── tools/call (guard_validate) ──────────▶│  校验请求
        │◀─── tools/call result ────────────────────│
        │                                            │
        │──── ... more calls ... ──────────────────▶│
        │                                            │
        │──── shutdown ─────────────────────────────▶│  关闭
        │◀─── shutdown response ────────────────────│
```

### 1.2 initialize 握手

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "cursor",
      "version": "0.45.0"
    }
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": { "listChanged": true },
      "resources": { "subscribe": true }
    },
    "serverInfo": {
      "name": "agentguard-mcp",
      "version": "0.1.0"
    }
  }
}
```

### 1.3 tools/list — 工具发现

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "guard_validate",
        "description": "Validate AI output through AI Output Guard's three-layer progressive guard (Schema → Semantic → Policy). Returns pass/deny/fix/warn/ask_human result.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "output": {
              "type": "string",
              "description": "The AI output text to validate"
            },
            "context": {
              "type": "object",
              "description": "Optional context for policy evaluation",
              "properties": {
                "agent": { "type": "string" },
                "environment": { "type": "string" },
                "user": { "type": "string" }
              }
            }
          },
          "required": ["output"]
        }
      },
      {
        "name": "guard_set_policy",
        "description": "Dynamically update the active policy rules. Policy takes effect immediately for subsequent validations.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "policy": {
              "type": "string",
              "description": "Policy YAML content or file path"
            }
          },
          "required": ["policy"]
        }
      },
      {
        "name": "guard_get_audit",
        "description": "Query audit log entries",
        "inputSchema": {
          "type": "object",
          "properties": {
            "limit": {
              "type": "integer",
              "description": "Maximum entries to return (default 20)",
              "default": 20
            },
            "level": {
              "type": "string",
              "enum": ["pass", "warn", "fix", "ask_human", "deny"],
              "description": "Filter by result level"
            }
          }
        }
      },
      {
        "name": "guard_status",
        "description": "Get current AI Output Guard configuration and runtime status",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      },
      {
        "name": "guard_add_intent",
        "description": "Add a custom dangerous intent pattern at runtime",
        "inputSchema": {
          "type": "object",
          "properties": {
            "name": {
              "type": "string",
              "description": "Intent name (e.g., 'custom_api_call')"
            },
            "patterns": {
              "type": "array",
              "items": { "type": "string" },
              "description": "Regex patterns for rule matching"
            }
          },
          "required": ["name"]
        }
      }
    ]
  }
}
```

### 1.4 guard_validate — 校验调用

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "guard_validate",
    "arguments": {
      "output": "{\"action\": \"execute_sql\", \"query\": \"DROP TABLE users\"}",
      "context": {
        "agent": "openclaw",
        "environment": "production"
      }
    }
  }
}
```

**响应（DENY）**：
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "🛑 DENIED by semantic guard\n\nMatched dangerous intent: drop_table (rule match, confidence: 100%)\nPattern: \\bDROP\\s+TABLE\\b\n\nThe AI output contains a DROP TABLE statement which is prohibited by security policy.\n\nAudit ID: ag-a1b2c3d4e5f6\nDuration: 0.8ms"
      }
    ],
    "isError": false
  }
}
```

**响应（PASS with FIX）**：
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "✅ PASSED (auto-fixed) by schema guard\n\nFix: method value \"DELTE\" auto-corrected to \"DELETE\" (confidence: 95%)\n\nFixed output:\n{\"endpoint\": \"/api/users\", \"method\": \"DELETE\", \"params\": {}}\n\nAudit ID: ag-f1e2d3c4b5a6\nDuration: 1.2ms"
      }
    ],
    "isError": false
  }
}
```

### 1.5 MCP Resources

**读取当前策略**：
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "resources/read",
  "params": {
    "uri": "agentguard://policy"
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "contents": [
      {
        "uri": "agentguard://policy",
        "mimeType": "text/yaml",
        "text": "version: \"1.0\"\ndefaults:\n  on_no_match: allow\nrules:\n  ..."
      }
    ]
  }
}
```

### 1.6 策略热更新通知

当策略文件变更时，Server 主动推送通知：

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

客户端收到后重新调用 `tools/list` 获取最新工具列表。

---

## 二、LSP Server 协议流程

### 2.1 连接生命周期

```
VS Code / JetBrains                   AI Output Guard LSP Server
        │                                      │
        │──── initialize ──────────────────────▶│
        │◀─── initialize response ─────────────│
        │     (capabilities: diag + codeAction) │
        │                                      │
        │──── textDocument/didOpen ────────────▶│  文档打开
        │                                      │
        │◀─── textDocument/publishDiagnostics ─│  诊断推送
        │                                      │
        │──── textDocument/didChange ──────────▶│  文档编辑
        │                                      │
        │◀─── textDocument/publishDiagnostics ─│  增量诊断
        │                                      │
        │──── textDocument/codeAction ─────────▶│  请求修正
        │◀─── codeAction response ─────────────│  提供修正建议
        │                                      │
        │──── workspace/executeCommand ────────▶│  执行修正
        │◀─── executeCommand result ───────────│
        │                                      │
        │──── textDocument/didClose ───────────▶│  文档关闭
```

### 2.2 initialize 握手

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "processId": 12345,
    "rootUri": "file:///Users/dev/project",
    "capabilities": {
      "textDocument": {
        "publishDiagnostics": { "relatedInformation": true },
        "codeAction": { "codeActionLiteralSupport": {} }
      }
    }
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "capabilities": {
      "textDocumentSync": {
        "openClose": true,
        "change": 1,
        "save": true
      },
      "diagnosticProvider": {
        "interFileDependencies": false,
        "workspaceDiagnostics": false
      },
      "codeActionProvider": {
        "codeActionKinds": ["quickfix", "agentguard.fix", "agentguard.suggest"]
      },
      "hoverProvider": true,
      "codeLensProvider": {}
    }
  }
}
```

### 2.3 publishDiagnostics — 安全标注推送

当 AI 生成的内容包含安全问题时，LSP Server 推送诊断：

```json
{
  "jsonrpc": "2.0",
  "method": "textDocument/publishDiagnostics",
  "params": {
    "uri": "file:///Users/dev/project/agent_output.py",
    "diagnostics": [
      {
        "range": {
          "start": { "line": 42, "character": 30 },
          "end": { "line": 42, "character": 52 }
        },
        "severity": 1,
        "source": "AI Output Guard",
        "code": "SEMANTIC_DROP_TABLE",
        "message": "🛑 Dangerous intent detected: drop_table\n\nThe AI output contains a DROP TABLE SQL statement.\nPattern: \\bDROP\\s+TABLE\\b\nConfidence: 100%",
        "relatedInformation": [
          {
            "location": {
              "uri": "file:///Users/dev/project/policy.yaml",
              "range": { "start": { "line": 8, "character": 0 }, "end": { "line": 12, "character": 0 } }
            },
            "message": "Matched rule: 禁止 DROP/TRUNCATE 操作"
          }
        ],
        "tags": [1],
        "data": {
          "guardLevel": "deny",
          "auditId": "ag-a1b2c3d4e5f6",
          "layer": "semantic",
          "intent": "drop_table"
        }
      }
    ]
  }
}
```

**Severity 映射**：

| GuardLevel | LSP DiagnosticSeverity | 视觉效果 |
|:---|:---|:---|
| DENY | 1 (Error) | 🔴 红色波浪线 |
| ASK_HUMAN | 2 (Warning) | 🟡 黄色波浪线 + 💡 图标 |
| WARN | 2 (Warning) | 🟡 黄色波浪线 |
| FIX | 3 (Information) | 🔵 蓝色波浪线 |
| PASS | — | 无标注 |

### 2.4 codeAction — 快速修正

**请求**：
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "textDocument/codeAction",
  "params": {
    "textDocument": { "uri": "file:///Users/dev/project/agent_output.py" },
    "range": { "start": { "line": 42, "character": 30 }, "end": { "line": 42, "character": 52 } },
    "context": {
      "diagnostics": [
        {
          "code": "SCHEMA_ENUM_FIX",
          "message": "method value \"DELTE\" auto-corrected to \"DELETE\""
        }
      ]
    }
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "result": [
    {
      "title": "🔧 Fix: DELTE → DELETE (auto-correct)",
      "kind": "quickfix",
      "diagnostics": [{ "code": "SCHEMA_ENUM_FIX" }],
      "edit": {
        "changes": {
          "file:///Users/dev/project/agent_output.py": [
            {
              "range": {
                "start": { "line": 42, "character": 35 },
                "end": { "line": 42, "character": 40 }
              },
              "newText": "DELETE"
            }
          ]
        }
      },
      "command": {
        "title": "Accept fix",
        "command": "agentguard.acceptFix",
        "arguments": ["ag-f1e2d3c4b5a6"]
      }
    },
    {
      "title": "📋 View guard details",
      "kind": "agentguard.suggest",
      "command": {
        "title": "Show details",
        "command": "agentguard.showDetails",
        "arguments": ["ag-f1e2d3c4b5a6"]
      }
    }
  ]
}
```

### 2.5 CodeLens — 安全状态标签

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "textDocument/codeLens",
  "params": {
    "textDocument": { "uri": "file:///Users/dev/project/agent_output.py" }
  }
}
```

**响应**：
```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "result": [
    {
      "range": {
        "start": { "line": 42, "character": 0 },
        "end": { "line": 42, "character": 0 }
      },
      "command": {
        "title": "🛡️ AI Output Guard: DENIED (drop_table)",
        "command": "agentguard.showDetails",
        "arguments": ["ag-a1b2c3d4e5f6"]
      }
    }
  ]
}
```

---

## 三、API Proxy 协议流程

### 3.1 请求处理生命周期

```
AI 工具 (Cursor)                   AI Output Guard Proxy                  LLM API (OpenAI)
      │                                   │                                │
      │── POST /v1/chat/completions ─────▶│                                │
      │   (原始请求)                       │                                │
      │                                   │── 识别: 是 LLM API? ──▶ YES   │
      │                                   │── 记录请求 ID ──▶ req-001     │
      │                                   │                                │
      │                                   │── POST /v1/chat/completions ──▶│
      │                                   │   (原样转发)                    │
      │                                   │                                │
      │                                   │◀── 200 OK ───────────────────│
      │                                   │   (LLM 响应)                   │
      │                                   │                                │
      │                                   │── 提取输出文本 ──▶ "DROP..."   │
      │                                   │── Guard 校验 ──▶ DENY          │
      │                                   │                                │
      │◀── 200 OK ──────────────────────│                                │
      │   (修改后响应 + Guard Header)      │                                │
```

### 3.2 透明转发（非 LLM 请求）

```
AI 工具                              AI Output Guard Proxy
      │                                   │
      │── GET /api/some-endpoint ────────▶│
      │                                   │── 识别: 非 LLM API ──▶ 透传
      │                                   │── GET /api/some-endpoint ──────▶ 目标服务器
      │                                   │◀── 响应 ──────────────────────│
      │◀── 原样响应 ─────────────────────│
```

### 3.3 完整请求示例

**客户端发送**：
```http
POST /v1/chat/completions HTTP/1.1
Host: api.openai.com
Content-Type: application/json
Authorization: Bearer sk-xxx

{
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "Write SQL to delete all users"}
  ]
}
```

**Proxy 转发给 OpenAI**（原样转发，添加追踪 Header）：
```http
POST /v1/chat/completions HTTP/1.1
Host: api.openai.com
Content-Type: application/json
Authorization: Bearer sk-xxx
X-AI Output Guard-Request-Id: req-001

{
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "Write SQL to delete all users"}
  ]
}
```

**OpenAI 返回**：
```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "chatcmpl-abc123",
  "choices": [
    {
      "message": {
        "content": "```sql\nDROP TABLE users;\n```"
      },
      "finish_reason": "stop"
    }
  ]
}
```

**Proxy 校验后返回（DENY）**：
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-AI Output Guard-Status: blocked
X-AI Output Guard-Reason: semantic_drop_table
X-AI Output Guard-Audit-Id: ag-a1b2c3d4e5f6
X-AI Output Guard-Confidence: 1.0

{
  "id": "chatcmpl-abc123",
  "choices": [
    {
      "message": {
        "content": "⚠️ [AI Output Guard] This output was blocked: Dangerous intent detected (drop_table). The AI suggested a DROP TABLE statement which is prohibited by security policy. Audit ID: ag-a1b2c3d4e5f6"
      },
      "finish_reason": "stop"
    }
  ]
}
```

### 3.4 FIX 场景（自动修正后放行）

**Proxy 返回（FIX）**：
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-AI Output Guard-Status: fixed
X-AI Output Guard-Reason: schema_enum_fix
X-AI Output Guard-Audit-Id: ag-f1e2d3c4b5a6
X-AI Output Guard-Fix-Description: "DELTE" → "DELETE"

{
  "id": "chatcmpl-abc123",
  "choices": [
    {
      "message": {
        "content": "{\"endpoint\": \"/api/users\", \"method\": \"DELETE\", \"params\": {}}"
      },
      "finish_reason": "stop"
    }
  ]
}
```

### 3.5 健康检查

```http
GET /health HTTP/1.1
Host: localhost:8080
```

**响应**：
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "guard": {
    "semantic_mode": "rule",
    "policy_rules": 5,
    "intents": ["drop_table", "execute_shell", "access_secret"]
  },
  "stats": {
    "total_requests": 1234,
    "llm_requests": 567,
    "blocked": 23,
    "fixed": 12,
    "passed": 532,
    "avg_guard_duration_ms": 1.2
  }
}
```

### 3.6 错误场景

**Guard 超时（Fail-Open）**：
```http
HTTP/1.1 200 OK
X-AI Output Guard-Status: timeout
X-AI Output Guard-Warning: Guard validation timed out, passed through
X-AI Output Guard-Audit-Id: ag-t1m30ut0000

{ 原始 LLM 响应不变 }
```

**LLM API 不可达**：
```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json

{
  "error": "AI Output Guard Proxy: Failed to reach upstream LLM API",
  "upstream_url": "https://api.openai.com/v1/chat/completions",
  "request_id": "req-001"
}
```

---

## 四、跨协议统一行为

### 4.1 审计 ID 格式

所有协议的审计 ID 格式统一：`ag-{12位hex}`

- MCP: 在 tool result 文本中包含
- LSP: 在 diagnostic.data.auditId 中包含
- CLI: 在 JSON 输出和 human 格式中包含
- API Proxy: 在 `X-AI Output Guard-Audit-Id` Header 中包含

### 4.2 错误降级一致性

所有协议共享相同的降级行为：

| 场景 | MCP | LSP | CLI | API Proxy |
|:---|:---|:---|:---|:---|
| Guard 超时 | 返回 WARN 结果 | 无诊断 | 退出码 0 + WARN | 透传 + X-Warning Header |
| Guard 内部错误 | 返回 WARN 结果 | 无诊断 | 退出码 3 | 透传 + X-Error Header |
| 策略文件无效 | 初始化时报错 | 初始化时报错 | 退出码 4 | 启动失败 |
| LLM API 不可达 | N/A | N/A | N/A | 502 Bad Gateway |

### 4.3 配置共享

MCP / LSP / CLI / API Proxy 共享同一套配置系统：

```bash
# 所有协议都读取相同的配置来源
# 1. 环境变量 AGENTGUARD_*
# 2. .agentguard.yaml
# 3. ~/.agentguard/config.yaml
# 4. 内置默认值

# MCP Server 启动时读取
npx agentguard-mcp --policy ./policy.yaml

# LSP Server 启动时读取（VS Code 设置覆盖）
# vscode settings: agentguard.policyPath

# CLI 直接指定
agentguard check --policy ./policy.yaml "..."

# API Proxy 启动时读取
docker run -e AGENTGUARD_POLICY=/app/policy.yaml agentguard/proxy
```
