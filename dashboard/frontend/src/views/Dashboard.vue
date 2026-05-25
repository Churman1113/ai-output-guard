<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { getStatus, getAudit } from "../api/client";
import type { GuardStatus, AuditResponse, StatCard } from "../api/types";

const status = ref<GuardStatus | null>(null);
const audit = ref<AuditResponse | null>(null);
const loading = ref(true);

const levelCounts = computed(() => {
  const counts: Record<string, number> = {
    pass: 0,
    deny: 0,
    warn: 0,
    fix: 0,
    ask_human: 0,
  };
  if (audit.value?.entries) {
    for (const entry of audit.value.entries) {
      counts[entry.result] = (counts[entry.result] || 0) + 1;
    }
  }
  return counts;
});

const totalValidations = computed(() => {
  const c = levelCounts.value;
  return c.pass + c.deny + c.warn + c.fix + c.ask_human;
});

const passRate = computed(() => {
  if (totalValidations.value === 0) return 0;
  return Math.round((levelCounts.value.pass / totalValidations.value) * 100);
});

const denyRate = computed(() => {
  if (totalValidations.value === 0) return 0;
  return Math.round((levelCounts.value.deny / totalValidations.value) * 100);
});

const statCards = computed<StatCard[]>(() => [
  {
    title: "Total Validations",
    value: totalValidations.value,
    color: "text-gray-900",
  },
  {
    title: "Pass Rate",
    value: `${passRate.value}%`,
    color: "text-green-600",
    trend: passRate.value >= 80 ? "up" : "neutral",
  },
  {
    title: "Blocked",
    value: `${denyRate.value}%`,
    color: "text-red-600",
    trend: denyRate.value > 10 ? "down" : "neutral",
  },
  {
    title: "Active Rules",
    value: status.value?.policy?.rules ?? 0,
    color: "text-blue-600",
  },
]);

const recentEntries = computed(() => {
  return audit.value?.entries?.slice(0, 10) ?? [];
});

onMounted(async () => {
  try {
    const [s, a] = await Promise.all([getStatus(), getAudit(100)]);
    status.value = s;
    audit.value = a;
  } catch {
    // API not available
  } finally {
    loading.value = false;
  }
});

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
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Dashboard</h2>
      <p class="text-gray-500 mt-1">
        Guard status and validation statistics
      </p>
    </header>

    <!-- Loading state -->
    <div
      v-if="loading"
      class="text-center py-12 text-gray-400 animate-pulse"
    >
      Loading dashboard data...
    </div>

    <!-- Empty state -->
    <div v-else-if="!status && !audit" class="text-center py-12">
      <p class="text-gray-500">
        ⚠️ Cannot connect to AI Output Guard API.
      </p>
      <p class="text-sm text-gray-400 mt-2">
        Start the API server with:
        <code class="bg-gray-100 px-2 py-0.5 rounded text-xs">
          agentguard-api
        </code>
      </p>
    </div>

    <template v-else>
      <!-- Stat cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div
          v-for="card in statCards"
          :key="card.title"
          class="stat-card"
        >
          <p class="stat-label">{{ card.title }}</p>
          <p class="stat-value" :class="card.color">
            {{ card.value }}
          </p>
          <p v-if="card.trend" class="text-xs mt-1">
            <span
              v-if="card.trend === 'up'"
              class="text-green-500"
            >↑</span>
            <span
              v-else-if="card.trend === 'down'"
              class="text-red-500"
            >↓</span>
          </p>
        </div>
      </div>

      <!-- Guard layers status -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div class="card">
          <div class="card-header">Guard Layers</div>
          <div class="card-body space-y-4">
            <div
              v-for="(enabled, layer) in (status?.layers ?? {})"
              :key="layer"
              class="flex items-center justify-between"
            >
              <span class="capitalize text-gray-700">{{ layer }}</span>
              <span
                class="text-sm font-medium"
                :class="enabled ? 'text-green-600' : 'text-gray-400'"
              >
                {{ enabled ? "✅ Active" : "⏸️ Disabled" }}
              </span>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">Configuration</div>
          <div class="card-body space-y-3">
            <div class="flex justify-between">
              <span class="text-gray-500">Auto-fix</span>
              <span
                :class="
                  status?.config?.auto_fix
                    ? 'text-green-600'
                    : 'text-gray-400'
                "
              >
                {{ status?.config?.auto_fix ? "Enabled" : "Disabled" }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Fail-open</span>
              <span
                :class="
                  status?.config?.fail_open
                    ? 'text-green-600'
                    : 'text-gray-400'
                "
              >
                {{ status?.config?.fail_open ? "Enabled" : "Disabled" }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">On-fail action</span>
              <span class="text-gray-700">{{ status?.config?.on_fail }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-gray-500">Semantic mode</span>
              <span class="text-gray-700">{{
                status?.config?.semantic_mode
              }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="card">
        <div class="card-header">Recent Validations</div>
        <div class="card-body">
          <div v-if="recentEntries.length === 0" class="text-gray-400 text-sm text-center py-8">
            No validation data yet. Start using AI Output Guard to see results here.
          </div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="text-left text-gray-500 border-b border-gray-100">
                <th class="pb-3 font-medium">Time</th>
                <th class="pb-3 font-medium">Result</th>
                <th class="pb-3 font-medium">Blocked By</th>
                <th class="pb-3 font-medium">Input</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="entry in recentEntries"
                :key="entry.timestamp"
                class="border-b border-gray-50 hover:bg-gray-50"
              >
                <td class="py-2.5 text-gray-400 text-xs">
                  {{ new Date(Number(entry.timestamp) * 1000).toLocaleString() }}
                </td>
                <td class="py-2.5">
                  <span :class="badgeClass(entry.result)">
                    {{ entry.result.toUpperCase() }}
                  </span>
                </td>
                <td class="py-2.5 text-gray-600">
                  {{ entry.blocked_by || "—" }}
                </td>
                <td class="py-2.5 text-gray-500 text-xs truncate max-w-xs">
                  {{ entry.input_preview.slice(0, 60) }}...
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
