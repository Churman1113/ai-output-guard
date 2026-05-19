/**
 * Integration tests for the AgentGuard HTTP client.
 *
 * Spins up a mock HTTP server that mimics the Python guard daemon API
 * and tests all client functions: validate, fetchAudit, fetchStatus, healthCheck.
 *
 * Uses Node.js built-in test runner (available since Node 18).
 */

import * as http from "http";
import { describe, it, before, after } from "node:test";
import * as assert from "assert";
import {
  validate,
  fetchAudit,
  fetchStatus,
  healthCheck,
  GuardConfig,
} from "../src/guardClient";

// ── Mock Server ──

let server: http.Server;
let serverUrl: string;
let requestLog: { url: string; method: string; body: string }[] = [];

function startMockServer(): Promise<void> {
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
            res.end(
              JSON.stringify({
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
              })
            );
          } else if (parsed.output?.includes("rm -rf")) {
            res.writeHead(200);
            res.end(
              JSON.stringify({
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
              })
            );
          } else {
            res.writeHead(200);
            res.end(
              JSON.stringify({
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
              })
            );
          }
          return;
        }

        // Route: /api/v1/audit
        if (req.url?.startsWith("/api/v1/audit") && req.method === "GET") {
          res.writeHead(200);
          res.end(
            JSON.stringify({
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
            })
          );
          return;
        }

        // Route: /api/v1/status
        if (req.url === "/api/v1/status" && req.method === "GET") {
          res.writeHead(200);
          res.end(
            JSON.stringify({
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
            })
          );
          return;
        }

        // Unknown route
        res.writeHead(404);
        res.end(JSON.stringify({ status: "error", message: "Not found" }));
      });
    });

    server.listen(0, () => {
      const addr = server.address() as { port: number };
      serverUrl = `http://127.0.0.1:${addr.port}`;
      resolve();
    });
  });
}

function stopMockServer(): Promise<void> {
  return new Promise((resolve) => {
    if (server) {
      server.close(() => resolve());
    } else {
      resolve();
    }
  });
}

function makeConfig(overrides?: Partial<GuardConfig>): GuardConfig {
  return {
    guardDaemonUrl: serverUrl,
    enableSemantic: true,
    dangerousIntents: [],
    ...overrides,
  };
}

// ── Tests ──

describe("GuardClient HTTP", () => {
  before(async () => {
    requestLog = [];
    await startMockServer();
  });

  after(async () => {
    await stopMockServer();
  });

  describe("validate()", () => {
    it("should pass safe output", async () => {
      const result = await validate("hello world", makeConfig());
      assert.strictEqual(result.passed, true);
      assert.strictEqual(result.blocked, false);
      assert.strictEqual(result.level, "pass");
      assert.strictEqual(result.blocked_by, null);
      assert.strictEqual(result.latency_ms, 1.2);
    });

    it("should block SQL injection", async () => {
      const result = await validate("DROP TABLE users", makeConfig());
      assert.strictEqual(result.passed, false);
      assert.strictEqual(result.blocked, true);
      assert.strictEqual(result.level, "deny");
      assert.strictEqual(result.blocked_by, "semantic");
      assert.strictEqual(result.checks[0].layer, "semantic");
      assert.strictEqual(result.checks[0].message, "Dangerous intent: SQL injection");
    });

    it("should block dangerous commands", async () => {
      const result = await validate("rm -rf /etc", makeConfig());
      assert.strictEqual(result.blocked, true);
      assert.strictEqual(result.blocked_by, "schema");
    });

    it("should send dangerousIntents in context", async () => {
      const config = makeConfig({ dangerousIntents: ["data_destruction"] });
      await validate("test", config);
      // Verify the request was made to the right endpoint
      const lastReq = requestLog[requestLog.length - 1];
      assert.strictEqual(lastReq.url, "/api/v1/validate");
      assert.strictEqual(lastReq.method, "POST");
    });

    it("should throw on daemon error (non-200)", async () => {
      const badConfig = makeConfig({ guardDaemonUrl: `${serverUrl}/nonexistent` });
      await assert.rejects(
        () => validate("test", badConfig),
        /404|AgentGuard daemon error/
      );
    });

    it("should timeout for unreachable daemon", async () => {
      const deadConfig = makeConfig({ guardDaemonUrl: "http://127.0.0.1:19999" });
      await assert.rejects(
        () => validate("test", deadConfig),
        /fetch failed|timeout|ECONNREFUSED/
      );
    });
  });

  describe("fetchAudit()", () => {
    it("should return audit entries", async () => {
      const result = await fetchAudit(makeConfig());
      assert.strictEqual(result.total, 3);
      assert.strictEqual(result.shown, 3);
      assert.strictEqual(result.entries.length, 3);
      assert.strictEqual(result.entries[0].result, "deny");
    });

    it("should return structured entry with checks", async () => {
      const result = await fetchAudit(makeConfig());
      const entry = result.entries[1];
      assert.strictEqual(entry.result, "pass");
      assert.strictEqual(entry.blocked_by, null);
      assert.ok(entry.checks.length > 0);
    });
  });

  describe("fetchStatus()", () => {
    it("should return daemon status", async () => {
      const result = await fetchStatus(makeConfig());
      assert.strictEqual(result.server, "agentguard-api");
      assert.strictEqual(result.version, "0.1.0");
      assert.strictEqual(result.layers.schema, true);
      assert.strictEqual(result.layers.semantic, true);
      assert.strictEqual(result.layers.policy, false);
      assert.strictEqual(result.audit_entries, 42);
    });
  });

  describe("healthCheck()", () => {
    it("should return true for healthy daemon", async () => {
      const result = await healthCheck(makeConfig());
      assert.strictEqual(result, true);
    });

    it("should return false for unreachable daemon", async () => {
      const deadConfig = makeConfig({ guardDaemonUrl: "http://127.0.0.1:19999" });
      const result = await healthCheck(deadConfig);
      assert.strictEqual(result, false);
    });
  });
});
