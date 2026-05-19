"use strict";
/**
 * AgentGuard HTTP API client — communicates with the Python guard daemon.
 *
 * Calls the Phase 3a FastAPI server (agentguard-daemon) over HTTP.
 * Uses Node.js built-in fetch (available since Node 18).
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.validate = validate;
exports.fetchAudit = fetchAudit;
exports.fetchStatus = fetchStatus;
exports.healthCheck = healthCheck;
/**
 * Validate AI-generated text through the AgentGuard HTTP API.
 *
 * Calls POST /api/v1/validate on the guard daemon.
 *
 * @param text - The AI-generated text to validate.
 * @param config - Guard client configuration.
 * @returns GuardResult with pass/block decision and check details.
 */
async function validate(text, config) {
    const url = `${config.guardDaemonUrl}/api/v1/validate`;
    const body = { output: text };
    if (config.dangerousIntents.length > 0) {
        body["context"] = { dangerous_intents: config.dangerousIntents };
    }
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) {
        throw new Error(`AgentGuard daemon error (${response.status}): ${await response.text()}`);
    }
    const data = await response.json();
    return data;
}
/**
 * Fetch the guard daemon's audit log.
 *
 * Calls GET /api/v1/audit on the guard daemon.
 *
 * @param config - Guard client configuration.
 * @param limit - Maximum entries to return (default 50).
 * @param level - Optional filter by result level (pass/warn/deny/fix/ask_human).
 */
async function fetchAudit(config, limit = 50, level) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (level) {
        params.set("level", level);
    }
    const url = `${config.guardDaemonUrl}/api/v1/audit?${params}`;
    const response = await fetch(url, {
        method: "GET",
        signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) {
        throw new Error(`AgentGuard audit error (${response.status}): ${await response.text()}`);
    }
    return (await response.json());
}
/**
 * Check the guard daemon's status.
 *
 * Calls GET /api/v1/status on the guard daemon.
 *
 * @param config - Guard client configuration.
 */
async function fetchStatus(config) {
    const url = `${config.guardDaemonUrl}/api/v1/status`;
    const response = await fetch(url, {
        method: "GET",
        signal: AbortSignal.timeout(3_000),
    });
    if (!response.ok) {
        throw new Error(`AgentGuard status error (${response.status}): ${await response.text()}`);
    }
    return (await response.json());
}
/**
 * Check if the guard daemon is reachable.
 *
 * Calls GET /api/v1/health on the guard daemon.
 *
 * @param config - Guard client configuration.
 * @returns true if the daemon is healthy.
 */
async function healthCheck(config) {
    try {
        const url = `${config.guardDaemonUrl}/api/v1/health`;
        const response = await fetch(url, {
            method: "GET",
            signal: AbortSignal.timeout(2_000),
        });
        return response.ok;
    }
    catch {
        return false;
    }
}
//# sourceMappingURL=guardClient.js.map