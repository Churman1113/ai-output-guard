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
