/**
 * AgentGuard HTTP API client — communicates with the Python guard daemon.
 *
 * Calls the Phase 3a FastAPI server (agentguard-daemon) over HTTP.
 * Uses Node.js built-in fetch (available since Node 18).
 */

/**
 * Result from a single guard check layer.
 */
export interface GuardCheck {
  layer: string;
  level: string;
  message: string;
  confidence: number;
}

/**
 * Result from the AgentGuard validation pipeline.
 */
export interface GuardResult {
  passed: boolean;
  blocked: boolean;
  level: string;
  blocked_by: string | null;
  checks: GuardCheck[];
  latency_ms: number;
  context?: Record<string, string>;
  fixed_output?: string;
}

/**
 * A single audit log entry from the guard daemon.
 */
export interface AuditEntry {
  timestamp: number;
  result: string;
  blocked_by: string | null;
  input_preview: string;
  output_preview: string;
  checks: GuardCheck[];
}

/**
 * Audit log response from GET /api/v1/audit.
 */
export interface AuditResponse {
  total: number;
  shown: number;
  entries: AuditEntry[];
}

/**
 * Status response from GET /api/v1/status.
 */
export interface GuardStatus {
  server: string;
  version: string;
  layers: Record<string, boolean>;
  config: Record<string, unknown>;
  policy?: Record<string, unknown>;
  policy_path?: string;
  audit_entries: number;
}

/**
 * Configuration for the Guard HTTP client.
 */
export interface GuardConfig {
  /** URL of the AgentGuard daemon (default: http://127.0.0.1:8765) */
  guardDaemonUrl: string;
  /** Path to a YAML policy file */
  policyPath?: string;
  /** Enable semantic checking */
  enableSemantic: boolean;
  /** Dangerous intents to block */
  dangerousIntents: string[];
}

/**
 * Validate AI-generated text through the AgentGuard HTTP API.
 *
 * Calls POST /api/v1/validate on the guard daemon.
 *
 * @param text - The AI-generated text to validate.
 * @param config - Guard client configuration.
 * @returns GuardResult with pass/block decision and check details.
 */
export async function validate(
  text: string,
  config: GuardConfig
): Promise<GuardResult> {
  const url = `${config.guardDaemonUrl}/api/v1/validate`;

  const body: Record<string, unknown> = { output: text };
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
    throw new Error(
      `AgentGuard daemon error (${response.status}): ${await response.text()}`
    );
  }

  const data = await response.json();
  return data as GuardResult;
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
export async function fetchAudit(
  config: GuardConfig,
  limit: number = 50,
  level?: string
): Promise<AuditResponse> {
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
    throw new Error(
      `AgentGuard audit error (${response.status}): ${await response.text()}`
    );
  }

  return (await response.json()) as AuditResponse;
}

/**
 * Check the guard daemon's status.
 *
 * Calls GET /api/v1/status on the guard daemon.
 *
 * @param config - Guard client configuration.
 */
export async function fetchStatus(config: GuardConfig): Promise<GuardStatus> {
  const url = `${config.guardDaemonUrl}/api/v1/status`;

  const response = await fetch(url, {
    method: "GET",
    signal: AbortSignal.timeout(3_000),
  });

  if (!response.ok) {
    throw new Error(
      `AgentGuard status error (${response.status}): ${await response.text()}`
    );
  }

  return (await response.json()) as GuardStatus;
}

/**
 * Check if the guard daemon is reachable.
 *
 * Calls GET /api/v1/health on the guard daemon.
 *
 * @param config - Guard client configuration.
 * @returns true if the daemon is healthy.
 */
export async function healthCheck(config: GuardConfig): Promise<boolean> {
  try {
    const url = `${config.guardDaemonUrl}/api/v1/health`;
    const response = await fetch(url, {
      method: "GET",
      signal: AbortSignal.timeout(2_000),
    });
    return response.ok;
  } catch {
    return false;
  }
}
