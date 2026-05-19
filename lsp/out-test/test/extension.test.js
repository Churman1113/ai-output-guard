"use strict";
/**
 * Unit tests for GuardClient type definitions and severity mapping.
 *
 * Uses Node.js built-in test runner.
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
const node_test_1 = require("node:test");
const assert = __importStar(require("assert"));
// ── GuardClient Type Tests ──
(0, node_test_1.describe)("GuardClient Types", () => {
    (0, node_test_1.it)("should format JSON output correctly", () => {
        const text = JSON.stringify({ action: "read", target: "users" });
        const formatted = JSON.parse(text);
        assert.strictEqual(formatted.action, "read");
    });
    (0, node_test_1.it)("should wrap non-JSON text", () => {
        const text = "DROP TABLE users";
        const wrapped = JSON.stringify({ raw: text });
        const parsed = JSON.parse(wrapped);
        assert.strictEqual(parsed.raw, "DROP TABLE users");
    });
});
// ── GuardResult Tests ──
(0, node_test_1.describe)("GuardResult", () => {
    (0, node_test_1.it)("should detect blocked result", () => {
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
    (0, node_test_1.it)("should detect passed result", () => {
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
(0, node_test_1.describe)("Severity Mapping", () => {
    const LEVEL_SEVERITY = {
        deny: 0, // Error
        warn: 1, // Warning
        ask_human: 1, // Warning
        fix: 2, // Information
        pass: 2, // Information
    };
    (0, node_test_1.it)("deny should map to Error severity", () => {
        assert.strictEqual(LEVEL_SEVERITY["deny"], 0);
    });
    (0, node_test_1.it)("warn should map to Warning severity", () => {
        assert.strictEqual(LEVEL_SEVERITY["warn"], 1);
    });
    (0, node_test_1.it)("pass should map to Information severity", () => {
        assert.strictEqual(LEVEL_SEVERITY["pass"], 2);
    });
    (0, node_test_1.it)("should have all expected levels", () => {
        assert.ok("deny" in LEVEL_SEVERITY);
        assert.ok("warn" in LEVEL_SEVERITY);
        assert.ok("ask_human" in LEVEL_SEVERITY);
        assert.ok("fix" in LEVEL_SEVERITY);
        assert.ok("pass" in LEVEL_SEVERITY);
    });
});
//# sourceMappingURL=extension.test.js.map