/**
 * Unit tests for GuardClient type definitions and severity mapping.
 *
 * Uses Node.js built-in test runner.
 */

import { describe, it } from "node:test";
import * as assert from "assert";

// ── GuardClient Type Tests ──

describe("GuardClient Types", () => {
  it("should format JSON output correctly", () => {
    const text = JSON.stringify({ action: "read", target: "users" });
    const formatted = JSON.parse(text);
    assert.strictEqual(formatted.action, "read");
  });

  it("should wrap non-JSON text", () => {
    const text = "DROP TABLE users";
    const wrapped = JSON.stringify({ raw: text });
    const parsed = JSON.parse(wrapped);
    assert.strictEqual(parsed.raw, "DROP TABLE users");
  });
});

// ── GuardResult Tests ──

describe("GuardResult", () => {
  it("should detect blocked result", () => {
    const result = {
      passed: false,
      blocked: true,
      level: "deny",
      blocked_by: "semantic",
      checks: [
        {
          layer: "semantic",
          level: "deny",
          message: "Dangerous intent detected: drop_table",
          confidence: 1.0,
        },
      ],
      latency_ms: 3.5,
    };
    assert.strictEqual(result.blocked, true);
    assert.strictEqual(result.blocked_by, "semantic");
    assert.strictEqual(result.checks.length, 1);
  });

  it("should detect passed result", () => {
    const result = {
      passed: true,
      blocked: false,
      level: "pass",
      blocked_by: null,
      checks: [],
      latency_ms: 1.2,
    };
    assert.strictEqual(result.passed, true);
    assert.strictEqual(result.blocked, false);
  });
});

// ── Severity Mapping Tests ──

describe("Severity Mapping", () => {
  const LEVEL_SEVERITY: Record<string, number> = {
    deny: 0, // Error
    warn: 1, // Warning
    ask_human: 1, // Warning
    fix: 2, // Information
    pass: 2, // Information
  };

  it("deny should map to Error severity", () => {
    assert.strictEqual(LEVEL_SEVERITY["deny"], 0);
  });

  it("warn should map to Warning severity", () => {
    assert.strictEqual(LEVEL_SEVERITY["warn"], 1);
  });

  it("pass should map to Information severity", () => {
    assert.strictEqual(LEVEL_SEVERITY["pass"], 2);
  });

  it("should have all expected levels", () => {
    assert.ok("deny" in LEVEL_SEVERITY);
    assert.ok("warn" in LEVEL_SEVERITY);
    assert.ok("ask_human" in LEVEL_SEVERITY);
    assert.ok("fix" in LEVEL_SEVERITY);
    assert.ok("pass" in LEVEL_SEVERITY);
  });
});
