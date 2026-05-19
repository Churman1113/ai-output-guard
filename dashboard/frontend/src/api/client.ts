import type {
  GuardStatus,
  ValidateResponse,
  AuditResponse,
} from "./types";

const API_BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API Error (${res.status}): ${error}`);
  }

  return res.json();
}

export async function getStatus(): Promise<GuardStatus> {
  return request("/status");
}

export async function validate(
  output: string
): Promise<ValidateResponse> {
  return request("/validate", {
    method: "POST",
    body: JSON.stringify({ output }),
  });
}

export async function getAudit(
  limit = 50,
  level?: string
): Promise<AuditResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) params.set("level", level);
  return request(`/audit?${params}`);
}

export async function validateFile(
  filePath: string
): Promise<ValidateResponse> {
  return request("/validate", {
    method: "POST",
    body: JSON.stringify({ output: filePath, context: { source: "file" } }),
  });
}

/** 更新策略 YAML */
export async function updatePolicy(
  policyYaml: string
): Promise<{ status: string; rules_loaded: number; message: string }> {
  return request("/policy", {
    method: "POST",
    body: JSON.stringify({ policy: policyYaml }),
  });
}

/** 添加自定义意图 */
export async function addIntent(data: {
  name: string;
  category: string;
  severity: string;
  patterns: string[];
  description?: string;
}): Promise<{ status: string; message: string }> {
  return request("/intents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** 获取健康检查状态 */
export async function getHealth(): Promise<{
  status: string;
  server: string;
  version: string;
}> {
  return request("/health");
}

/** 导出审计日志（与 getAudit 相同端点，用于导出场景） */
export async function exportAudit(
  limit?: number,
  level?: string
): Promise<AuditResponse> {
  return getAudit(limit ?? 50, level);
}
