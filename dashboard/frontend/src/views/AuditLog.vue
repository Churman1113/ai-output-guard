<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { getAudit } from "../api/client";
import type { AuditEntry } from "../api/types";

const entries = ref<AuditEntry[]>([]);
const total = ref(0);
const loading = ref(true);
const filterLevel = ref<string>("");
const pageSize = 20;

const filteredEntries = computed(() => {
  if (!filterLevel.value) return entries.value;
  return entries.value.filter((e) => e.result === filterLevel.value);
});

onMounted(async () => {
  try {
    const result = await getAudit(100);
    entries.value = result.entries;
    total.value = result.total;
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

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Audit Log</h2>
      <p class="text-gray-500 mt-1">
        All guard validation events — {{ total }} total entries
      </p>
    </header>

    <!-- Filters -->
    <div class="flex gap-3 mb-6">
      <button
        class="btn-secondary text-sm"
        :class="{ 'bg-guard-50 border-guard-300': !filterLevel }"
        @click="filterLevel = ''"
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
        @click="filterLevel = level"
      >
        {{ level }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12 text-gray-400 animate-pulse">
      Loading audit entries...
    </div>

    <!-- Empty -->
    <div
      v-else-if="filteredEntries.length === 0"
      class="text-center py-12 text-gray-400"
    >
      No audit entries found.
    </div>

    <!-- Table -->
    <div v-else class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-gray-50 text-left text-gray-500">
              <th class="px-6 py-3 font-medium">Timestamp</th>
              <th class="px-6 py-3 font-medium">Result</th>
              <th class="px-6 py-3 font-medium">Blocked By</th>
              <th class="px-6 py-3 font-medium">Input</th>
              <th class="px-6 py-3 font-medium">Output</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="entry in filteredEntries"
              :key="entry.timestamp"
              class="border-t border-gray-100 hover:bg-gray-50"
            >
              <td class="px-6 py-3 text-gray-400 text-xs whitespace-nowrap">
                {{ formatTime(entry.timestamp) }}
              </td>
              <td class="px-6 py-3">
                <span :class="badgeClass(entry.result)">
                  {{ entry.result.toUpperCase() }}
                </span>
              </td>
              <td class="px-6 py-3 text-gray-600">
                {{ entry.blocked_by || "—" }}
              </td>
              <td class="px-6 py-3 text-gray-500 text-xs max-w-xs truncate">
                {{ entry.input_preview.slice(0, 80) }}
              </td>
              <td class="px-6 py-3 text-gray-500 text-xs max-w-xs truncate">
                {{ entry.output_preview.slice(0, 80) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
