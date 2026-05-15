#!/usr/bin/env python3
"""
AgentGuard Killer Demo — 5 分钟展示三层递进校验

运行方式:
    pip install agentguard
    python killer-demo.py

或（开发中，直接从源码运行）:
    python killer-demo.py
"""

import json
import time
from typing import Optional

# ──────────────────────────────────────────────
# 模拟 AgentGuard 核心（开发完成前用此模拟）
# ──────────────────────────────────────────────

class GuardLevel:
    PASS = "✅ PASS"
    DENY = "🛑 DENY"
    FIX = "🔧 FIX"
    WARN = "⚠️ WARN"
    ASK_HUMAN = "👤 ASK_HUMAN"


class DemoGuard:
    """AgentGuard 模拟实现 — 用于 Demo 展示"""

    # ── 内置规则 ──
    DANGEROUS_RULES = {
        "drop_table": [r"\bDROP\s+TABLE\b", r"\bTRUNCATE\s+TABLE\b"],
        "delete_all": [r"\bDELETE\s+FROM\s+\w+\s*;?\s*$", r"\brm\s+-rf\s+/"],
        "execute_shell": [r"\bsudo\s+", r"\bchmod\s+777\b", r"\bsu\s+root\b"],
        "access_secret": [r"\b(api[_-]?key|secret|password|token)\b"],
    }

    # ── 内置策略 ──
    POLICY_RULES = [
        {
            "name": "禁止访问生产数据库",
            "condition": lambda d: "/prod/" in str(d.get("endpoint", "")),
            "action": "deny",
            "message": "策略禁止访问生产环境",
        },
        {
            "name": "敏感操作需人工确认",
            "condition": lambda d: d.get("method") == "DELETE" and d.get("params", {}).get("scope") == "all",
            "action": "ask_human",
            "message": "正在执行批量删除，是否继续？",
        },
    ]

    # ── 枚举修正表 ──
    ENUM_FIXES = {
        "DELTE": "DELETE",
        "DELEET": "DELETE",
        "GT": "GET",
        "GETE": "GET",
        "POTS": "POST",
        "PTU": "PUT",
        "PATCh": "PATCH",
    }

    def validate(self, output: str, context: Optional[dict] = None) -> dict:
        """三层递进校验"""
        import re

        start = time.monotonic()
        checks = []

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Layer 1: Schema Guard — 结构校验
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        # 1a. JSON 解析
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            checks.append({
                "layer": "schema",
                "passed": False,
                "level": GuardLevel.DENY,
                "message": "JSON 解析失败",
            })
            return self._finalize(output, checks, GuardLevel.DENY, "schema", start)

        # 1b. 字段存在性
        if "endpoint" not in data and "action" not in data:
            checks.append({
                "layer": "schema",
                "passed": False,
                "level": GuardLevel.DENY,
                "message": "缺少必要字段: endpoint 或 action",
            })
            return self._finalize(output, checks, GuardLevel.DENY, "schema", start)

        # 1c. 枚举修正
        method = data.get("method", "")
        if method in self.ENUM_FIXES:
            fixed_method = self.ENUM_FIXES[method]
            data["method"] = fixed_method
            output = json.dumps(data, ensure_ascii=False)
            checks.append({
                "layer": "schema",
                "passed": False,
                "level": GuardLevel.FIX,
                "message": f"枚举值自动修正: {method} → {fixed_method}",
                "fix": output,
            })
        else:
            checks.append({
                "layer": "schema",
                "passed": True,
                "level": GuardLevel.PASS,
                "message": "结构校验通过",
            })

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Layer 2: Semantic Guard — 语义校验
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        for intent_name, patterns in self.DANGEROUS_RULES.items():
            for pattern in patterns:
                if re.search(pattern, output, re.IGNORECASE):
                    checks.append({
                        "layer": "semantic",
                        "passed": False,
                        "level": GuardLevel.DENY,
                        "message": f"匹配到危险意图: {intent_name}",
                        "pattern": pattern,
                    })
                    return self._finalize(output, checks, GuardLevel.DENY, "semantic", start)

        checks.append({
            "layer": "semantic",
            "passed": True,
            "level": GuardLevel.PASS,
            "message": "语义校验通过",
        })

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Layer 3: Policy Guard — 策略校验
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        for rule in self.POLICY_RULES:
            if rule["condition"](data):
                level = GuardLevel.ASK_HUMAN if rule["action"] == "ask_human" else GuardLevel.DENY
                checks.append({
                    "layer": "policy",
                    "passed": False,
                    "level": level,
                    "message": f"策略命中: {rule['name']} — {rule['message']}",
                })
                return self._finalize(output, checks, level, "policy", start)

        checks.append({
            "layer": "policy",
            "passed": True,
            "level": GuardLevel.PASS,
            "message": "策略校验通过",
        })

        return self._finalize(output, checks, GuardLevel.PASS, None, start)

    def _finalize(self, raw, checks, final_level, blocked_by, start):
        return {
            "raw": raw,
            "level": final_level,
            "checks": checks,
            "blocked_by": blocked_by,
            "duration_ms": round((time.monotonic() - start) * 1000, 2),
        }


# ──────────────────────────────────────────────
# Demo 场景
# ──────────────────────────────────────────────

def print_result(scenario: str, result: dict):
    """美观地打印校验结果"""
    print(f"\n{'='*60}")
    print(f"📋 场景: {scenario}")
    print(f"{'='*60}")
    print(f"📥 输入: {result['raw'][:80]}{'...' if len(result['raw']) > 80 else ''}")
    print(f"📤 判定: {result['level']}")
    if result['blocked_by']:
        print(f"🔒 拦截层: {result['blocked_by']}")
    print(f"⏱️  耗时: {result['duration_ms']}ms")
    print(f"\n{'─'*60}")
    for i, check in enumerate(result['checks'], 1):
        icon = "✅" if check['passed'] else ("🔧" if check['level'] == GuardLevel.FIX else "🛑")
        print(f"  Layer {i} [{check['layer']}] {icon} {check['message']}")
        if not check['passed'] and check.get('fix'):
            print(f"         修正后: {check['fix'][:60]}")
    print(f"{'─'*60}")


def main():
    guard = DemoGuard()

    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🛡️  AgentGuard — AI 输出安全引擎 Demo                      ║
║                                                              ║
║   三层递进校验: Schema → Semantic → Policy                   ║
║   The seatbelt between LLMs and your systems                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 1: 安全输出 — 三层全部通过
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"endpoint": "/api/users", "method": "GET", "params": {"limit": 10}}'
    )
    print_result("✅ 安全输出 — 正常 API 查询", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 2: Schema 修正 — 枚举拼写错误
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"endpoint": "/api/users", "method": "DELTE", "params": {}}'
    )
    print_result("🔧 Schema 修正 — method 拼写错误自动修正", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 3: 语义拦截 — DROP TABLE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"action": "execute_sql", "query": "DROP TABLE users"}'
    )
    print_result("🛑 语义拦截 — 检测到 DROP TABLE 危险操作", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 4: 语义拦截 — rm -rf
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"action": "execute_command", "command": "rm -rf /var/log/app"}'
    )
    print_result("🛑 语义拦截 — 检测到 rm -rf 危险命令", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 5: 策略拦截 — 访问生产环境
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"endpoint": "/prod/database", "method": "POST", "params": {"query": "INSERT INTO logs VALUES (...)"}}'
    )
    print_result("🛑 策略拦截 — 禁止访问生产环境", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 6: 策略人工确认 — 批量删除
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"endpoint": "/api/users", "method": "DELETE", "params": {"scope": "all"}}'
    )
    print_result("👤 策略确认 — 批量删除需人工确认", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 7: Schema 失败 — JSON 解析错误
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{endpoint: /api/users, method: GET}'  # 无引号，无效 JSON
    )
    print_result("🛑 Schema 失败 — JSON 解析错误", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 场景 8: 凭据泄露 — API Key 暴露
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    result = guard.validate(
        '{"action": "http_request", "url": "https://api.example.com", "headers": {"api_key": "sk-abc123def456ghi789jkl012mno345pqr678"}}'
    )
    print_result("🛑 语义拦截 — 检测到 API Key 泄露", result)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 汇总
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n{'='*60}")
    print("📊 Demo 汇总")
    print(f"{'='*60}")
    print("  ✅ 场景 1: 安全输出 → PASS")
    print("  🔧 场景 2: Schema 修正 → FIX (DELTE → DELETE)")
    print("  🛑 场景 3: DROP TABLE → DENY (语义层)")
    print("  🛑 场景 4: rm -rf → DENY (语义层)")
    print("  🛑 场景 5: 生产环境 → DENY (策略层)")
    print("  👤 场景 6: 批量删除 → ASK_HUMAN (策略层)")
    print("  🛑 场景 7: JSON 错误 → DENY (Schema 层)")
    print("  🛑 场景 8: API Key → DENY (语义层)")
    print(f"{'='*60}")
    print("""
💡 核心价值：
   • 三层递进：Schema → Semantic → Policy，前一层通过才进入下一层
   • 自动修正：拼写错误自动修复，减少无意义的拦截
   • 规则优先：确定性模式零延迟零误报，不依赖 ML 模型
   • 策略灵活：YAML 声明式策略，支持 deny/allow/ask_human

🚀 5 分钟上手：
   pip install agentguard
   from agentguard import Guard
   guard = Guard(schema=MyModel, semantic=True, policy="policy.yaml")
   result = guard.validate(llm_output)
""")


if __name__ == "__main__":
    main()
