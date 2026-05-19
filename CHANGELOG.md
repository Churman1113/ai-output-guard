# Changelog

## v0.1.0 (2026-05-15)

### Added
- **Python SDK**: Three-layer progressive guard (Schema → Semantic → Policy)
  - Schema Guard: Pydantic v2 + JSON Schema validation with auto-fix
  - Semantic Guard: 25 built-in dangerous intent patterns (keyword + regex + heuristic)
  - Policy Guard: YAML DSL engine with 14 operators, `all`/`any` combinators, 5 actions
  - Auto-fix: Enum Levenshtein matching, type coercion, nested object repair
- **CLI**: Typer command-line tool with Rich formatting
- **MCP Server**: JSON-RPC 2.0 protocol for AI IDE integration (5 tools + 2 resources)
- **API Proxy**: Zero-intrusion HTTP forward proxy for LLM API calls
  - OpenAI, Anthropic, Gemini, DeepSeek, Tongyi route detection
  - Response modification: PASS/FIX/WARN/DENY/ASK_HUMAN with X-AgentGuard-* headers
  - Docker deployment with health checks
- **REST API**: FastAPI HTTP server with validate/policy/audit/status endpoints
- **VS Code Extension**: Real-time diagnostic annotations for dangerous AI output
- **Dashboard**: Vue 3 + Vite web UI for audit logs, policies, and statistics
- **Audit System**: In-memory/file audit logging with per-request tracking
- **Comprehensive Tests**: 300+ test cases across all modules
- **Documentation**: Product definition, architecture, API reference, policy templates

### Phase Roadmap
- Phase 1: Python SDK + CLI + Tests ✅
- Phase 2: MCP Server ✅
- Phase 2.5: Schema Guard Enhancement (nested fix, advanced type coercion, matching) ✅
- Phase 3: API Proxy (zero-intrusion) ✅
- Phase 3b: LSP/VS Code Extension ✅
- Phase 4: Dashboard + PyPI Release ✅
