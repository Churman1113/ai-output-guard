/** API response types for AI Output Guard Dashboard */

export interface GuardCheck {
  layer: string;
  level: string;
  message: string;
  confidence: number;
}

export interface ValidateResponse {
  passed: boolean;
  blocked: boolean;
  level: string;
  blocked_by: string | null;
  checks: GuardCheck[];
  latency_ms: number;
  context?: Record<string, unknown>;
  fixed_output?: string;
}

export interface AuditEntry {
  timestamp: string;
  result: string;
  blocked_by: string | null;
  input_preview: string;
  output_preview: string;
  checks: string;
}

export interface AuditResponse {
  total: number;
  shown: number;
  entries: AuditEntry[];
}

export interface GuardConfig {
  auto_fix: boolean;
  fail_open: boolean;
  on_fail: string;
  semantic_mode: string;
}

export interface GuardStatus {
  server: string;
  version: string;
  layers: {
    schema: boolean;
    semantic: boolean;
    policy: boolean;
  };
  config: GuardConfig;
  policy: {
    rules: number;
    version: string;
    defaults: Record<string, string>;
  } | null;
  policy_path: string | null;
  audit_entries: number;
}

export interface StatCard {
  title: string;
  value: string | number;
  change?: string;
  trend?: "up" | "down" | "neutral";
  color: string;
}
