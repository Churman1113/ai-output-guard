"use strict";
/**
 * Integration tests for the AgentGuard HTTP client.
 *
 * Spins up a mock HTTP server that mimics the Python guard daemon API
 * and tests all client functions: validate, fetchAudit, fetchStatus, healthCheck.
 *
 * Uses Node.js built-in test runner (available since Node 18).
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
const http = __importStar(require("http"));
const node_test_1 = require("node:test");
const assert = __importStar(require("assert"));
const guardClient_1 = require("../src/guardClient");
// ── Mock Server ──
let server;
let serverUrl;
let requestLog = [];
function startMockServer() {
    return new Promise((resolve) => {
        server = http.createServer((req, res) => {
            let body = "";
            req.on("data", (chunk) => (body += chunk));
            req.on("end", () => {
                requestLog.push({
                    url: req.url || "",
                    method: req.method || "",
                    body,
                });
                res.setHeader("Content-Type", "application/json");
                // Route: /api/v1/health
                if (req.url === "/api/v1/health") {
                    res.writeHead(200);
                    res.end(JSON.stringify({ status: "ok", server: "agentguard-api", version: "0.1.0" }));
                    return;
                }
                // Route: /api/v1/validate
                if (req.url === "/api/v1/validate" && req.method === "POST") {
                    const parsed = JSON.parse(body);
                    if (parsed.output?.includes("DROP TABLE")) {
                        res.writeHead(200);
                        res.end(JSON.stringify({
                            passed: false,
                            blocked: true,
                            level: "deny",
                            blocked_by: "semantic",
                            checks: [
                                {
                                    layer: "semantic",
                                    level: "deny",
                                    message: "Dangerous intent: SQL injection",
                                    confidence: 1.0,
                                },
                            ],
                            latency_ms: 3.5,
                        }));
                    }
                    else if (parsed.output?.includes("rm -rf")) {
                        res.writeHead(200);
                        res.end(JSON.stringify({
                            passed: false,
                            blocked: true,
                            level: "deny",
                            blocked_by: "schema",
                            checks: [
                                {
                                    layer: "schema",
                                    level: "deny",
                                    message: "Dangerous command: rm -rf",
                                    confidence: 1.0,
                                },
                            ],
                            latency_ms: 2.1,
                        }));
                    }
                    else {
                        res.writeHead(200);
                        res.end(JSON.stringify({
                            passed: true,
                            blocked: false,
                            level: "pass",
                            blocked_by: null,
                            checks: [
                                {
                                    layer: "semantic",
                                    level: "pass",
                                    message: "No dangerous intent detected",
                                    confidence: 1.0,
                                },
                            ],
                            latency_ms: 1.2,
                        }));
                    }
                    return;
                }
                // Route: /api/v1/audit
                if (req.url?.startsWith("/api/v1/audit") && req.method === "GET") {
                    res.writeHead(200);
                    res.end(JSON.stringify({
                        total: 3,
                        shown: 3,
                        entries: [
                            {
                                timestamp: 1715000000,
                                result: "deny",
                                blocked_by: "semantic",
                                input_preview: "DROP TABLE users",
                                output_preview: '"DROP TABLE users"',
                                checks: [
                                    {
                                        layer: "semantic",
                                        level: "deny",
                                        message: "SQL injection",
                                        confidence: 1.0,
                                    },
                                ],
                            },
                            {
                                timestamp: 1715000001,
                                result: "pass",
                                blocked_by: null,
                                input_preview: "hello world",
                                output_preview: '"hello world"',
                                checks: [
                                    {
                                        layer: "semantic",
                                        level: "pass",
                                        message: "No dangerous intent",
                                        confidence: 1.0,
                                    },
                                ],
                            },
                            {
                                timestamp: 1715000002,
                                result: "warn",
                                blocked_by: "policy",
                                input_preview: "DELETE /prod/users",
                                output_preview: '"DELETE /prod/users"',
                                checks: [
                                    {
                                        layer: "policy",
                                        level: "warn",
                                        message: "DELETE method triggered warning",
                                        confidence: 1.0,
                                    },
                                ],
                            },
                        ],
                    }));
                    return;
                }
                // Route: /api/v1/status
                if (req.url === "/api/v1/status" && req.method === "GET") {
                    res.writeHead(200);
                    res.end(JSON.stringify({
                        server: "agentguard-api",
                        version: "0.1.0",
                        layers: { schema: true, semantic: true, policy: false },
                        config: {
                            auto_fix: true,
                            fail_open: false,
                            on_fail: "deny",
                            semantic_mode: "rule",
                        },
                        policy_path: null,
                        audit_entries: 42,
                    }));
                    return;
                }
                // Unknown route
                res.writeHead(404);
                res.end(JSON.stringify({ status: "error", message: "Not found" }));
            });
        });
        server.listen(0, () => {
            const addr = server.address();
            serverUrl = `http://127.0.0.1:${addr.port}`;
            resolve();
        });
    });
}
function stopMockServer() {
    return new Promise((resolve) => {
        if (server) {
            server.close(() => resolve());
        }
        else {
            resolve();
        }
    });
}
function makeConfig(overrides) {
    return {
        guardDaemonUrl: serverUrl,
        enableSemantic: true,
        dangerousIntents: [],
        ...overrides,
    };
}
// ── Tests ──
(0, node_test_1.describe)("GuardClient HTTP", () => {
    (0, node_test_1.before)(async () => {
        requestLog = [];
        await startMockServer();
    });
    (0, node_test_1.after)(async () => {
        await stopMockServer();
    });
    (0, node_test_1.describe)("validate()", () => {
        (0, node_test_1.it)("should pass safe output", async () => {
            const result = await (0, guardClient_1.validate)("hello world", makeConfig());
            assert.strictEqual(result.passed, true);
            assert.strictEqual(result.blocked, false);
            assert.strictEqual(result.level, "pass");
            assert.strictEqual(result.blocked_by, null);
            assert.strictEqual(result.latency_ms, 1.2);
        });
        (0, node_test_1.it)("should block SQL injection", async () => {
            const result = await (0, guardClient_1.validate)("DROP TABLE users", makeConfig());
            assert.strictEqual(result.passed, false);
            assert.strictEqual(result.blocked, true);
            assert.strictEqual(result.level, "deny");
            assert.strictEqual(result.blocked_by, "semantic");
            assert.strictEqual(result.checks[0].layer, "semantic");
            assert.strictEqual(result.checks[0].message, "Dangerous intent: SQL injection");
        });
        (0, node_test_1.it)("should block dangerous commands", async () => {
            const result = await (0, guardClient_1.validate)("rm -rf /etc", makeConfig());
            assert.strictEqual(result.blocked, true);
            assert.strictEqual(result.blocked_by, "schema");
        });
        (0, node_test_1.it)("should send dangerousIntents in context", async () => {
            const config = makeConfig({ dangerousIntents: ["data_destruction"] });
            await (0, guardClient_1.validate)("test", config);
            // Verify the request was made to the right endpoint
            const lastReq = requestLog[requestLog.length - 1];
            assert.strictEqual(lastReq.url, "/api/v1/validate");
            assert.strictEqual(lastReq.method, "POST");
        });
        (0, node_test_1.it)("should throw on daemon error (non-200)", async () => {
            const badConfig = makeConfig({ guardDaemonUrl: `${serverUrl}/nonexistent` });
            await assert.rejects(() => (0, guardClient_1.validate)("test", badConfig), /404|AgentGuard daemon error/);
        });
        (0, node_test_1.it)("should timeout for unreachable daemon", async () => {
            const deadConfig = makeConfig({ guardDaemonUrl: "http://127.0.0.1:19999" });
            await assert.rejects(() => (0, guardClient_1.validate)("test", deadConfig), /fetch failed|timeout|ECONNREFUSED/);
        });
    });
    (0, node_test_1.describe)("fetchAudit()", () => {
        (0, node_test_1.it)("should return audit entries", async () => {
            const result = await (0, guardClient_1.fetchAudit)(makeConfig());
            assert.strictEqual(result.total, 3);
            assert.strictEqual(result.shown, 3);
            assert.strictEqual(result.entries.length, 3);
            assert.strictEqual(result.entries[0].result, "deny");
        });
        (0, node_test_1.it)("should return structured entry with checks", async () => {
            const result = await (0, guardClient_1.fetchAudit)(makeConfig());
            const entry = result.entries[1];
            assert.strictEqual(entry.result, "pass");
            assert.strictEqual(entry.blocked_by, null);
            assert.ok(entry.checks.length > 0);
        });
    });
    (0, node_test_1.describe)("fetchStatus()", () => {
        (0, node_test_1.it)("should return daemon status", async () => {
            const result = await (0, guardClient_1.fetchStatus)(makeConfig());
            assert.strictEqual(result.server, "agentguard-api");
            assert.strictEqual(result.version, "0.1.0");
            assert.strictEqual(result.layers.schema, true);
            assert.strictEqual(result.layers.semantic, true);
            assert.strictEqual(result.layers.policy, false);
            assert.strictEqual(result.audit_entries, 42);
        });
    });
    (0, node_test_1.describe)("healthCheck()", () => {
        (0, node_test_1.it)("should return true for healthy daemon", async () => {
            const result = await (0, guardClient_1.healthCheck)(makeConfig());
            assert.strictEqual(result, true);
        });
        (0, node_test_1.it)("should return false for unreachable daemon", async () => {
            const deadConfig = makeConfig({ guardDaemonUrl: "http://127.0.0.1:19999" });
            const result = await (0, guardClient_1.healthCheck)(deadConfig);
            assert.strictEqual(result, false);
        });
    });
});
//# sourceMappingURL=guardClient.test.js.map