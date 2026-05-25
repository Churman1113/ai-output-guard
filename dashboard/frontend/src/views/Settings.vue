<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getStatus, getHealth, validate } from "../api/client";
import type { GuardStatus, ValidateResponse } from "../api/types";

// ========== 状态数据 ==========
const status = ref<GuardStatus | null>(null);
const loading = ref(true);

// ========== 健康检查 ==========
interface HealthInfo {
  status: string;
  server: string;
  version: string;
}

const healthInfo = ref<HealthInfo | null>(null);
const healthLoading = ref(false);
const healthError = ref<string | null>(null);

// ========== Try it Out 测试区 ==========
const testInput = ref("");
const testLoading = ref(false);
const testResult = ref<ValidateResponse | null>(null);
const testError = ref<string | null>(null);

// ========== 方法 ==========

/** 加载 Guard 状态 */
async function fetchStatus() {
  loading.value = true;
  try {
    status.value = await getStatus();
  } catch {
    // API 不可用
  } finally {
    loading.value = false;
  }
}

/** 执行健康检查 */
async function checkHealth() {
  healthLoading.value = true;
  healthError.value = null;
  healthInfo.value = null;
  try {
    healthInfo.value = await getHealth();
  } catch (e: unknown) {
    healthError.value =
      e instanceof Error ? e.message : "Health check failed.";
  } finally {
    healthLoading.value = false;
  }
}

/** Try it Out 验证测试 */
async function runTest() {
  if (!testInput.value.trim()) return;
  testLoading.value = true;
  testResult.value = null;
  testError.value = null;
  try {
    testResult.value = await validate(testInput.value.trim());
  } catch (e: unknown) {
    testError.value =
      e instanceof Error ? e.message : "Validation request failed.";
  } finally {
    testLoading.value = false;
  }
}

/** Badge 样式映射 */
function badgeClass(level: string): string {
  const map: Record<string, string> = {
    pass: "badge-pass",
    deny: "badge-deny",
    warn: "badge-warn",
    fix: "badge-fix",
    ask_human: "badge-ask_human",
  };
  return map[level] ?? "badge";
}

onMounted(() => {
  fetchStatus();
});
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Settings</h2>
      <p class="text-gray-500 mt-1">AI Output Guard configuration and diagnostics</p>
    </header>

    <!-- 加载状态 -->
    <div
      v-if="loading"
      class="text-center py-12 text-gray-400 animate-pulse"
    >
      Loading settings...
    </div>

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- Guard 配置 -->
        <div class="card">
          <div class="card-header">Guard Configuration</div>
          <div class="card-body space-y-4">
            <div v-if="status?.config" class="space-y-3">
              <div class="flex justify-between items-center">
                <span class="text-gray-500">Auto-fix</span>
                <span
                  :class="
                    status.config.auto_fix
                      ? 'text-green-600 font-medium'
                      : 'text-gray-400'
                  "
                >
                  {{ status.config.auto_fix ? "Enabled" : "Disabled" }}
                </span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-500">Fail-open</span>
                <span
                  :class="
                    status.config.fail_open
                      ? 'text-green-600 font-medium'
                      : 'text-gray-400'
                  "
                >
                  {{ status.config.fail_open ? "Enabled" : "Disabled" }}
                </span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-500">On-fail action</span>
                <span class="text-gray-700 font-medium">
                  {{ status.config.on_fail }}
                </span>
              </div>
              <div class="flex justify-between items-center">
                <span class="text-gray-500">Semantic mode</span>
                <span class="text-gray-700 font-medium">
                  {{ status.config.semantic_mode }}
                </span>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400">
              Unable to load configuration. Is the API running?
            </div>
          </div>
        </div>

        <!-- Guard Layers 状态 -->
        <div class="card">
          <div class="card-header">Guard Layers</div>
          <div class="card-body space-y-4">
            <div
              v-for="(enabled, layer) in (status?.layers ?? {})"
              :key="layer"
              class="flex items-center justify-between p-3 rounded-lg"
              :class="enabled ? 'bg-green-50' : 'bg-gray-50'"
            >
              <div class="flex items-center gap-3">
                <div
                  class="w-2.5 h-2.5 rounded-full"
                  :class="enabled ? 'bg-green-500' : 'bg-gray-300'"
                ></div>
                <span class="capitalize text-gray-700 font-medium">
                  {{ layer }}
                </span>
              </div>
              <span
                class="text-sm"
                :class="enabled ? 'text-green-600' : 'text-gray-400'"
              >
                {{ enabled ? "Active" : "Disabled" }}
              </span>
            </div>
            <div
              v-if="!status?.layers"
              class="text-sm text-gray-400 text-center py-4"
            >
              No layer information available.
            </div>
          </div>
        </div>

        <!-- 策略信息 -->
        <div class="card">
          <div class="card-header">Policy Information</div>
          <div class="card-body space-y-4">
            <div v-if="status?.policy || status?.policy_path">
              <div class="flex justify-between items-center">
                <span class="text-gray-500">Policy path</span>
                <span class="text-gray-700 text-sm font-mono">
                  {{ status.policy_path || "N/A" }}
                </span>
              </div>
              <div class="flex justify-between items-center mt-3">
                <span class="text-gray-500">Active rules</span>
                <span class="text-gray-700 font-medium">
                  {{ status?.policy?.rules ?? 0 }}
                </span>
              </div>
              <div class="flex justify-between items-center mt-3">
                <span class="text-gray-500">Policy version</span>
                <span class="text-gray-700 font-medium">
                  {{ status?.policy?.version ?? "N/A" }}
                </span>
              </div>
              <div
                v-if="status?.policy?.defaults"
                class="mt-4 pt-4 border-t border-gray-100"
              >
                <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                  Defaults
                </p>
                <div
                  v-for="(value, key) in status.policy.defaults"
                  :key="key"
                  class="flex justify-between text-sm"
                >
                  <span class="text-gray-400">{{ key }}</span>
                  <span class="text-gray-600">{{ value }}</span>
                </div>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400">
              No policy loaded.
            </div>
          </div>
        </div>

        <!-- 服务器信息 -->
        <div class="card">
          <div class="card-header">Server Information</div>
          <div class="card-body space-y-4">
            <div class="flex justify-between items-center">
              <span class="text-gray-500">Version</span>
              <span class="text-gray-700 font-mono text-sm">
                {{ status?.version ?? "N/A" }}
              </span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-gray-500">Server</span>
              <span class="text-gray-700 font-mono text-sm">
                {{ status?.server ?? "N/A" }}
              </span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-gray-500">Audit entries</span>
              <span class="text-gray-700 font-medium">
                {{ status?.audit_entries ?? 0 }}
              </span>
            </div>

            <div class="pt-4 border-t border-gray-100">
              <p class="text-xs text-gray-400">
                AI Output Guard — AI Output Safety Middleware
              </p>
              <p class="text-xs text-gray-400 mt-1">
                MIT License — github.com/Churman1113/ai-output-guard
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- API 健康检查 -->
      <div class="card mt-6">
        <div class="card-header flex items-center justify-between">
          <span>API Health Check</span>
          <button
            class="btn-secondary text-sm"
            :disabled="healthLoading"
            @click="checkHealth"
          >
            {{ healthLoading ? "Checking..." : "Run Health Check" }}
          </button>
        </div>
        <div class="card-body">
          <!-- 健康检查结果 -->
          <div v-if="healthInfo" class="space-y-3">
            <div
              class="flex items-center gap-3 p-4 rounded-lg"
              :class="
                healthInfo.status === 'ok'
                  ? 'bg-green-50 border border-green-200'
                  : 'bg-yellow-50 border border-yellow-200'
              "
            >
              <div
                class="w-3 h-3 rounded-full"
                :class="
                  healthInfo.status === 'ok' ? 'bg-green-500' : 'bg-yellow-500'
                "
              ></div>
              <div>
                <p class="font-medium text-sm" :class="healthInfo.status === 'ok' ? 'text-green-700' : 'text-yellow-700'">
                  {{ healthInfo.status === 'ok' ? 'Healthy' : 'Degraded' }}
                </p>
                <p class="text-xs text-gray-500 mt-0.5">
                  Server: {{ healthInfo.server }} | Version: {{ healthInfo.version }}
                </p>
              </div>
            </div>
          </div>

          <!-- 健康检查错误 -->
          <div v-else-if="healthError" class="p-4 rounded-lg bg-red-50 border border-red-200">
            <p class="text-sm text-red-700 font-medium">Health check failed</p>
            <p class="text-xs text-red-500 mt-1">{{ healthError }}</p>
          </div>

          <!-- 未检查提示 -->
          <div v-else class="text-sm text-gray-400 text-center py-4">
            Click "Run Health Check" to verify API connectivity.
          </div>
        </div>
      </div>

      <!-- Try it Out 测试区 -->
      <div class="card mt-6">
        <div class="card-header">Try it Out — API Connectivity Test</div>
        <div class="card-body space-y-4">
          <p class="text-sm text-gray-500">
            Send a test validation request to verify the API is working correctly.
          </p>
          <textarea
            v-model="testInput"
            rows="3"
            class="w-full px-4 py-3 border border-gray-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-guard-500 focus:border-transparent resize-y"
            placeholder="Enter text to validate..."
          ></textarea>
          <div class="flex items-center gap-3">
            <button
              class="btn-primary text-sm"
              :disabled="testLoading || !testInput.trim()"
              @click="runTest"
            >
              {{ testLoading ? "Sending..." : "Validate" }}
            </button>
            <span v-if="testError" class="text-red-500 text-sm">
              {{ testError }}
            </span>
          </div>

          <!-- 测试结果 -->
          <div v-if="testResult" class="mt-4">
            <div
              class="p-4 rounded-lg border"
              :class="
                testResult.passed
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              "
            >
              <div class="flex items-center gap-3 mb-2">
                <span :class="badgeClass(testResult.level)">
                  {{ testResult.level.toUpperCase() }}
                </span>
                <span
                  class="text-sm font-medium"
                  :class="testResult.passed ? 'text-green-700' : 'text-red-700'"
                >
                  {{ testResult.passed ? "PASSED" : "BLOCKED" }}
                </span>
                <span class="text-xs text-gray-400 ml-auto">
                  {{ testResult.latency_ms }}ms
                </span>
              </div>
              <p v-if="testResult.blocked_by" class="text-sm text-gray-600">
                Blocked by: <span class="font-medium">{{ testResult.blocked_by }}</span>
              </p>
              <p
                v-if="testResult.fixed_output"
                class="text-sm text-blue-600 mt-1"
              >
                Auto-fixed: {{ testResult.fixed_output.slice(0, 150) }}
                {{ testResult.fixed_output.length > 150 ? "..." : "" }}
              </p>
            </div>

            <!-- 检查详情 -->
            <div v-if="testResult.checks.length > 0" class="mt-3 space-y-2">
              <div
                v-for="(check, idx) in testResult.checks"
                :key="idx"
                class="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <span :class="badgeClass(check.level)">
                  {{ check.level.toUpperCase() }}
                </span>
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-gray-700">{{ check.message }}</p>
                  <p class="text-xs text-gray-400 mt-0.5">
                    Layer: {{ check.layer }} | Confidence: {{ (check.confidence * 100).toFixed(1) }}%
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
