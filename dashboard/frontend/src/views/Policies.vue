<script setup lang="ts">
import { ref, onMounted } from "vue";

interface Rule {
  name: string;
  action: string;
  priority: number;
  condition: string;
  message: string;
}

const policyYaml = ref(`version: "1.0"
defaults:
  on_no_match: allow
  on_error: pass

rules:
  - name: block-db-writes
    priority: 100
    condition:
      all:
        - field: action
          operator: in
          value: [DROP, DELETE, TRUNCATE, ALTER]
        - field: target
          operator: matches
          value: "*users*"
    action: deny
    message: "Database write operations blocked for user tables"

  - name: warn-large-response
    priority: 50
    condition:
      field: response_size
      operator: gt
      value: 1000000
    action: warn
    message: "Large response detected"
`);

const parsedRules = ref<Rule[]>([]);
const parseError = ref<string | null>(null);
const saved = ref(false);

const examplePolicies = [
  { name: "Production DB Safe", file: "production-db-safe.yaml" },
  { name: "Enterprise Compliance", file: "enterprise-compliance.yaml" },
  { name: "Development Lenient", file: "development-lenient.yaml" },
];

function parseYaml() {
  parseError.value = null;
  parsedRules.value = [];

  try {
    // Simple YAML-like parser for the dashboard display
    const lines = policyYaml.value.split("\n");
    const rules: Rule[] = [];
    let currentRule: Partial<Rule> | null = null;

    for (const line of lines) {
      const trimmed = line.trim();

      if (trimmed === "rules:") {
        continue;
      }

      if (trimmed.startsWith("- name:")) {
        if (currentRule?.name) {
          rules.push(currentRule as Rule);
        }
        currentRule = {
          name: trimmed.replace("- name:", "").trim().replace(/"/g, ""),
          action: "",
          priority: 0,
          condition: "",
          message: "",
        };
      }

      if (currentRule && trimmed.startsWith("action:")) {
        currentRule.action = trimmed.replace("action:", "").trim();
      }

      if (currentRule && trimmed.startsWith("priority:")) {
        currentRule.priority = parseInt(
          trimmed.replace("priority:", "").trim()
        );
      }

      if (currentRule && trimmed.startsWith("message:")) {
        currentRule.message = trimmed
          .replace("message:", "")
          .trim()
          .replace(/"/g, "");
      }
    }

    if (currentRule?.name) {
      rules.push(currentRule as Rule);
    }

    parsedRules.value = rules;
  } catch (e) {
    parseError.value = "Failed to parse policy YAML";
  }
}

function loadExample(name: string) {
  // In production, load from the examples directory
  policyYaml.value = `# Loading ${name}...
# In production, this would load from the policy file.
`;
  parseYaml();
}

function savePolicy() {
  parseYaml();
  saved.value = true;
  setTimeout(() => (saved.value = false), 2000);
}

onMounted(() => {
  parseYaml();
});

function actionColor(action: string): string {
  const map: Record<string, string> = {
    deny: "bg-red-100 text-red-700",
    allow: "bg-green-100 text-green-700",
    warn: "bg-yellow-100 text-yellow-700",
    ask_human: "bg-purple-100 text-purple-700",
    modify: "bg-blue-100 text-blue-700",
  };
  return map[action] ?? "bg-gray-100 text-gray-700";
}
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Policies</h2>
      <p class="text-gray-500 mt-1">
        Manage guard policy rules (YAML DSL)
      </p>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Editor -->
      <div class="lg:col-span-2 card">
        <div class="card-header flex items-center justify-between">
          <span>Policy Editor</span>
          <div class="flex gap-2">
            <button class="btn-secondary text-xs" @click="parseYaml">
              Validate
            </button>
            <button class="btn-primary text-xs" @click="savePolicy">
              {{ saved ? "✓ Saved" : "Save" }}
            </button>
          </div>
        </div>
        <div class="card-body">
          <textarea
            v-model="policyYaml"
            class="w-full h-96 font-mono text-sm p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-guard-500 focus:border-transparent"
            spellcheck="false"
          ></textarea>
          <p v-if="parseError" class="text-red-500 text-sm mt-2">
            {{ parseError }}
          </p>
          <p v-if="saved" class="text-green-600 text-sm mt-2">
            Policy saved successfully
          </p>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="space-y-6">
        <!-- Parsed rules -->
        <div class="card">
          <div class="card-header">Rules ({{ parsedRules.length }})</div>
          <div class="card-body space-y-3">
            <div
              v-for="rule in parsedRules"
              :key="rule.name"
              class="p-3 bg-gray-50 rounded-lg"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="font-medium text-sm">{{ rule.name }}</span>
                <span
                  class="text-xs px-2 py-0.5 rounded-full font-medium"
                  :class="actionColor(rule.action)"
                >
                  {{ rule.action }}
                </span>
              </div>
              <p class="text-xs text-gray-500">
                Priority: {{ rule.priority }}
              </p>
              <p v-if="rule.message" class="text-xs text-gray-400 mt-1">
                {{ rule.message }}
              </p>
            </div>
            <div
              v-if="parsedRules.length === 0"
              class="text-sm text-gray-400 text-center py-4"
            >
              No rules parsed
            </div>
          </div>
        </div>

        <!-- Templates -->
        <div class="card">
          <div class="card-header">Templates</div>
          <div class="card-body space-y-2">
            <button
              v-for="tmpl in examplePolicies"
              :key="tmpl.file"
              class="w-full text-left px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
              @click="loadExample(tmpl.name)"
            >
              📄 {{ tmpl.name }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
