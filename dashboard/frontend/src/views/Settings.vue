<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getStatus } from "../api/client";
import type { GuardStatus } from "../api/types";

const status = ref<GuardStatus | null>(null);
const apiUrl = ref("http://localhost:8765");
const autoRefresh = ref(true);
const refreshInterval = ref(10);
const saved = ref(false);

onMounted(async () => {
  try {
    status.value = await getStatus();
  } catch {
    // API not available
  }
});

function saveSettings() {
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
}
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Settings</h2>
      <p class="text-gray-500 mt-1">AgentGuard Dashboard configuration</p>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Connection settings -->
      <div class="card">
        <div class="card-header">API Connection</div>
        <div class="card-body space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              API URL
            </label>
            <input
              v-model="apiUrl"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
            />
            <p class="text-xs text-gray-400 mt-1">
              The AgentGuard HTTP API endpoint
            </p>
          </div>

          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium text-gray-700">Auto-refresh</p>
              <p class="text-xs text-gray-400">
                Automatically refresh dashboard data
              </p>
            </div>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                v-model="autoRefresh"
                type="checkbox"
                class="sr-only peer"
              />
              <div
                class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-guard-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-guard-600"
              ></div>
            </label>
          </div>

          <div v-if="autoRefresh">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Refresh interval (seconds)
            </label>
            <input
              v-model="refreshInterval"
              type="number"
              min="5"
              max="300"
              class="w-24 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
            />
          </div>

          <button class="btn-primary" @click="saveSettings">
            {{ saved ? "✓ Saved" : "Save Settings" }}
          </button>
        </div>
      </div>

      <!-- About -->
      <div class="card">
        <div class="card-header">About</div>
        <div class="card-body space-y-4">
          <div>
            <p class="text-sm font-medium text-gray-700">Version</p>
            <p class="text-sm text-gray-500">{{ status?.version ?? "0.1.0" }}</p>
          </div>
          <div>
            <p class="text-sm font-medium text-gray-700">Server</p>
            <p class="text-sm text-gray-500">{{ status?.server ?? "agentguard-api" }}</p>
          </div>
          <div>
            <p class="text-sm font-medium text-gray-700">Active Layers</p>
            <div class="flex gap-2 mt-1">
              <span
                v-for="(enabled, layer) in (status?.layers ?? {})"
                :key="layer"
                class="text-xs px-2 py-1 rounded-full"
                :class="
                  enabled
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-400'
                "
              >
                {{ layer }}
              </span>
            </div>
          </div>
          <div v-if="status?.policy">
            <p class="text-sm font-medium text-gray-700">Policy</p>
            <p class="text-sm text-gray-500">
              {{ status.policy.rules }} rules (v{{ status.policy.version }})
            </p>
          </div>
          <div class="pt-4 border-t border-gray-100">
            <p class="text-xs text-gray-400">
              AgentGuard — AI Output Safety Middleware
            </p>
            <p class="text-xs text-gray-400 mt-1">
              MIT License — github.com/agentguard/agentguard
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
