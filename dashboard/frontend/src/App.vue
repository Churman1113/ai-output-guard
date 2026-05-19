<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { getStatus } from "./api/client";
import type { GuardStatus } from "./api/types";

const router = useRouter();
const route = useRoute();
const status = ref<GuardStatus | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);

const navItems = [
  { path: "/", label: "Dashboard", icon: "📊" },
  { path: "/audit", label: "Audit Log", icon: "📋" },
  { path: "/policies", label: "Policies", icon: "🔒" },
  { path: "/settings", label: "Settings", icon: "⚙️" },
];

const levelColors: Record<string, string> = {
  pass: "text-green-600",
  deny: "text-red-600",
  warn: "text-yellow-600",
  fix: "text-blue-600",
  ask_human: "text-purple-600",
};

onMounted(async () => {
  try {
    status.value = await getStatus();
  } catch (e) {
    error.value = "Cannot connect to AgentGuard API. Make sure the server is running on port 8765.";
  } finally {
    loading.value = false;
  }
});

function isActive(path: string): boolean {
  return route.path === path;
}
</script>

<template>
  <div class="flex h-screen bg-gray-50">
    <!-- Sidebar -->
    <aside class="w-64 bg-white border-r border-gray-200 flex flex-col">
      <div class="p-6 border-b border-gray-100">
        <h1 class="text-xl font-bold text-gray-900 flex items-center gap-2">
          🛡️ AgentGuard
        </h1>
        <p class="text-xs text-gray-500 mt-1">AI Output Safety Dashboard</p>
      </div>

      <nav class="flex-1 p-4 space-y-1">
        <button
          v-for="item in navItems"
          :key="item.path"
          @click="router.push(item.path)"
          class="w-full text-left px-4 py-2.5 rounded-lg transition-colors flex items-center gap-3"
          :class="
            isActive(item.path)
              ? 'bg-guard-50 text-guard-700 font-medium'
              : 'text-gray-600 hover:bg-gray-100'
          "
        >
          <span>{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <!-- Connection status -->
      <div class="p-4 border-t border-gray-100">
        <div v-if="loading" class="text-xs text-gray-400">Connecting...</div>
        <div v-else-if="error" class="text-xs text-red-500">⚠️ Disconnected</div>
        <div v-else class="text-xs text-green-600 flex items-center gap-1">
          <span class="w-2 h-2 bg-green-500 rounded-full inline-block"></span>
          Connected — {{ status?.audit_entries ?? 0 }} entries
        </div>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-y-auto p-8">
      <router-view />
    </main>
  </div>
</template>
