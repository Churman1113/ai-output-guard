<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { getAudit, validate, exportAudit } from "../api/client";
import type { AuditEntry, ValidateResponse } from "../api/types";

// 审计日志状态
const entries = ref<AuditEntry[]>([]);
const total = ref(0);
const shown = ref(0);
const loading = ref(true);
const filterLevel = ref<string>("");
const limit = ref(50);

// 实时验证测试区状态
const testInput = ref("");
const testLoading = ref(false);
const testResult = ref<ValidateResponse | null>(null);
const testError = ref<string | null>(null);

// 筛选后的条目
const filteredEntries = computed(() => {
  if (!filterLevel.value) return entries.value;
  return entries.value.filter((e) => e.result === filterLevel.value);
});

// 分页信息
const pageInfo = computed(() => ({
  showing: filteredEntries.value.length,
  total: total.value,
}));

// 加载审计日志
async function fetchAudit() {
  loading.value = true;
  try {
    const result = await getAudit(
      limit.value,
      filterLevel.value || undefined
    );
    entries.value = result.entries;
    total.value = result.total;
    shown.value = result.shown;
  } catch {
    entries.value = [];
    total.value = 0;
    shown.value = 0;
  } finally {
    loading.value = false;
  }
}

// 切换筛选级别
function setFilter(level: string) {
  filterLevel.value = level;
  fetchAudit();
}

// 切换数量限制
function setLimit(val: number) {
  limit.value = val;
  fetchAudit();
}

// 刷新
function refresh() {
  fetchAudit();
}

// 导出为 JSON
async function exportJSON() {
  try {
    const data = await exportAudit(
      limit.value,
      filterLevel.value || undefined
    );
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agentguard-audit-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    alert("Failed to export audit log.");
  }
}

// 实时验证测试
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

// Badge 样式映射
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

// 格式化时间戳（支持数字秒和 ISO 字符串）
function formatTime(ts: string | number): string {
  const num = typeof ts === "string" ? new Date(ts).getTime() : ts * 1000;
  return new Date(num).toLocaleString();
}

// 截断文本
function truncate(text: string, max: number): string {
  if (!text) return "";
  return text.length > max ? text.slice(0, max) + "..." : text;
}

onMounted(() => {
  fetchAudit();
});
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Audit Log</h2>
      <p class="text-gray-500 mt-1">
        All guard validation events — {{ total }} total entries
      </p>
    </header>

    <!-- 筛选栏 -->
    <div class="card mb-6">
      <div class="card-body">
        <div class="flex flex-wrap items-center gap-4">
          <!-- 级别筛选按钮 -->
          <div class="flex gap-2">
            <button
              class="btn-secondary text-sm"
              :class="{ 'bg-guard-50 border-guard-300': !filterLevel }"
              @click="setFilter('')"
            >
              All
            </button>
            <button
              v-for="level in ['pass', 'deny', 'warn', 'fix', 'ask_human']"
              :key="level"
              class="btn-secondary text-sm capitalize"
              :class="{
                'bg-guard-50 border-guard-300': filterLevel === level,
              }"
              @click="setFilter(level)"
            >
              {{ level.replace("_", " ") }}
            </button>
          </div>

          <!-- 数量限制选择 -->
          <div class="flex items-center gap-2 ml-auto">
            <label class="text-sm text-gray-500">Limit:</label>
            <select
              :value="limit"
              class="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
              @change="setLimit(Number(($event.target as HTMLSelectElement).value))"
            >
              <option :value="20">20</option>
              <option :value="50">50</option>
              <option :value="100">100</option>
              <option :value="200">200</option>
            </select>
          </div>

          <!-- 操作按钮 -->
          <div class="flex gap-2">
            <button class="btn-secondary text-sm" @click="refresh">
              Refresh
            </button>
            <button class="btn-primary text-sm" @click="exportJSON">
              Export JSON
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div
      v-if="loading"
      class="text-center py-12 text-gray-400 animate-pulse"
    >
      Loading audit entries...
    </div>

    <!-- 空状态 -->
    <div
      v-else-if="filteredEntries.length === 0"
      class="text-center py-16"
    >
      <div class="text-gray-300 text-5xl mb-4">
        <svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <p class="text-gray-500 text-lg">No audit entries found.</p>
      <p class="text-gray-400 text-sm mt-1">
        Entries will appear here once AgentGuard starts processing validations.
      </p>
    </div>

    <!-- 审计日志表格 -->
    <template v-else>
      <div class="card overflow-hidden mb-4">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-gray-50 text-left text-gray-500">
                <th class="px-6 py-3 font-medium">Timestamp</th>
                <th class="px-6 py-3 font-medium">Result</th>
                <th class="px-6 py-3 font-medium">Blocked By</th>
                <th class="px-6 py-3 font-medium">Input Preview</th>
                <th class="px-6 py-3 font-medium">Output Preview</th>
                <th class="px-6 py-3 font-medium">Checks</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in filteredEntries"
                :key="entry.timestamp"
                class="border-t border-gray-100 hover:bg-gray-50 transition-colors"
              >
                <td class="px-6 py-3 text-gray-400 text-xs whitespace-nowrap">
                  {{ formatTime(entry.timestamp) }}
                </td>
                <td class="px-6 py-3">
                  <span :class="badgeClass(entry.result)">
                    {{ entry.result.toUpperCase() }}
                  </span>
                </td>
                <td class="px-6 py-3 text-gray-600 text-xs">
                  {{ entry.blocked_by || "\u2014" }}
                </td>
                <td
                  class="px-6 py-3 text-gray-500 text-xs max-w-[200px] truncate"
                  :title="entry.input_preview"
                >
                  {{ truncate(entry.input_preview, 80) }}
                </td>
                <td
                  class="px-6 py-3 text-gray-500 text-xs max-w-[200px] truncate"
                  :title="entry.output_preview"
                >
                  {{ truncate(entry.output_preview, 80) }}
                </td>
                <td
                  class="px-6 py-3 text-gray-400 text-xs max-w-[200px] truncate"
                  :title="entry.checks"
                >
                  {{ truncate(entry.checks, 60) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 分页信息 -->
      <div class="text-sm text-gray-400 text-right">
        Showing {{ pageInfo.showing }} of {{ pageInfo.total }} entries
      </div>
    </template>

    <!-- 实时验证测试区 -->
    <div class="card mt-8">
      <div class="card-header">Try it Out — Validate LLM Output</div>
      <div class="card-body space-y-4">
        <p class="text-sm text-gray-500">
          Paste an LLM output below to test the guard validation in real time.
        </p>
        <textarea
          v-model="testInput"
          rows="4"
          class="w-full px-4 py-3 border border-gray-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-guard-500 focus:border-transparent resize-y"
          placeholder="Enter LLM output to validate..."
        ></textarea>
        <div class="flex items-center gap-3">
          <button
            class="btn-primary text-sm"
            :disabled="testLoading || !testInput.trim()"
            @click="runTest"
          >
            {{ testLoading ? "Validating..." : "Validate" }}
          </button>
          <span v-if="testError" class="text-red-500 text-sm">
            {{ testError }}
          </span>
        </div>

        <!-- 验证结果 -->
        <div v-if="testResult" class="mt-4 space-y-3">
          <div
            class="p-4 rounded-lg border"
            :class="
              testResult.passed
                ? 'bg-green-50 border-green-200'
                : 'bg-red-50 border-red-200'
            "
          >
            <div class="flex items-center gap-3 mb-2">
              <span
                :class="badgeClass(testResult.level)"
              >
                {{ testResult.level.toUpperCase() }}
              </span>
              <span class="text-sm font-medium" :class="testResult.passed ? 'text-green-700' : 'text-red-700'">
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
              Auto-fixed output: {{ testResult.fixed_output.slice(0, 200) }}
              {{ testResult.fixed_output.length > 200 ? "..." : "" }}
            </p>
          </div>

          <!-- 检查详情 -->
          <div v-if="testResult.checks.length > 0" class="space-y-2">
            <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">
              Check Details
            </p>
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
  </div>
</template>
