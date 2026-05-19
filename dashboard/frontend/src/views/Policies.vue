<script setup lang="ts">
import { ref, onMounted } from "vue";
import { updatePolicy, addIntent } from "../api/client";

// ========== 策略编辑器 ==========
interface Rule {
  name: string;
  action: string;
  priority: number;
  condition: string;
  message: string;
}

const defaultPolicyYaml = `version: "1.0"
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

  - name: block-sql-injection
    priority: 200
    condition:
      any:
        - field: output
          operator: contains
          value: "DROP TABLE"
        - field: output
          operator: contains
          value: "UNION SELECT"
        - field: output
          operator: regex
          value: "';.*--"
    action: deny
    message: "Potential SQL injection detected in output"

  - name: limit-data-access
    priority: 80
    condition:
      field: target_table
      operator: in
      value: [users, payments, credentials]
    action: ask_human
    message: "Access to sensitive tables requires human approval"
`;

const policyYaml = ref(defaultPolicyYaml);
const parsedRules = ref<Rule[]>([]);
const parseError = ref<string | null>(null);
const saving = ref(false);
const saveMessage = ref<string | null>(null);
const rulesLoaded = ref<number | null>(null);

// ========== 自定义意图管理 ==========
interface CustomIntent {
  name: string;
  category: string;
  severity: string;
  patterns: string[];
  description: string;
}

const intentForm = ref({
  name: "",
  category: "security",
  severity: "high",
  patterns: "",
  description: "",
});

const customIntents = ref<CustomIntent[]>([]);
const addingIntent = ref(false);
const intentMessage = ref<string | null>(null);

// ========== 模板策略 ==========
const examplePolicies = [
  { name: "Production DB Safe", file: "production-db-safe.yaml" },
  { name: "Enterprise Compliance", file: "enterprise-compliance.yaml" },
  { name: "Development Lenient", file: "development-lenient.yaml" },
];

// ========== 策略编辑器方法 ==========

/** 简单解析 YAML 中的 rules 列表（仅用于前端展示） */
function parseYaml() {
  parseError.value = null;
  parsedRules.value = [];

  try {
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
  } catch {
    parseError.value = "Failed to parse policy YAML";
  }
}

/** 加载默认策略 */
function loadDefaultPolicy() {
  policyYaml.value = defaultPolicyYaml;
  parseYaml();
}

/** 加载示例策略模板 */
function loadExample(name: string) {
  policyYaml.value = `# ${name}\n# This is a template policy.\n# Customize it for your use case.\n\nversion: "1.0"\ndefaults:\n  on_no_match: allow\n  on_error: pass\n\nrules:\n  - name: example-rule\n    priority: 100\n    action: deny\n    message: "Example rule from ${name}"\n`;
  parseYaml();
}

/** 保存策略到后端 */
async function savePolicy() {
  saving.value = true;
  saveMessage.value = null;
  parseError.value = null;

  try {
    const result = await updatePolicy(policyYaml.value);
    rulesLoaded.value = result.rules_loaded;
    saveMessage.value = result.message || `${result.rules_loaded} rules active`;
    parseYaml();
  } catch (e: unknown) {
    parseError.value =
      e instanceof Error ? e.message : "Failed to save policy.";
  } finally {
    saving.value = false;
    // 3 秒后清除成功消息
    setTimeout(() => {
      saveMessage.value = null;
    }, 3000);
  }
}

// ========== 自定义意图方法 ==========

/** 添加自定义意图 */
async function handleAddIntent() {
  const { name, category, severity, patterns, description } = intentForm.value;

  if (!name.trim()) return;

  addingIntent.value = true;
  intentMessage.value = null;

  const patternsList = patterns
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);

  try {
    await addIntent({
      name: name.trim(),
      category,
      severity,
      patterns: patternsList,
      description: description.trim() || undefined,
    });

    customIntents.value.push({
      name: name.trim(),
      category,
      severity,
      patterns: patternsList,
      description: description.trim(),
    });

    // 重置表单
    intentForm.value = {
      name: "",
      category: "security",
      severity: "high",
      patterns: "",
      description: "",
    };
    intentMessage.value = "Intent added successfully.";
  } catch (e: unknown) {
    intentMessage.value =
      e instanceof Error ? e.message : "Failed to add intent.";
  } finally {
    addingIntent.value = false;
    setTimeout(() => {
      intentMessage.value = null;
    }, 3000);
  }
}

/** 移除自定义意图（仅前端列表） */
function removeIntent(index: number) {
  customIntents.value.splice(index, 1);
}

// ========== 辅助方法 ==========

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

function severityColor(severity: string): string {
  const map: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    medium: "bg-yellow-100 text-yellow-700",
    low: "bg-green-100 text-green-700",
  };
  return map[severity] ?? "bg-gray-100 text-gray-700";
}

onMounted(() => {
  parseYaml();
});
</script>

<template>
  <div>
    <header class="mb-8">
      <h2 class="text-2xl font-bold text-gray-900">Policies</h2>
      <p class="text-gray-500 mt-1">
        Manage guard policy rules and custom intents
      </p>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- 策略编辑器 -->
      <div class="lg:col-span-2 card">
        <div class="card-header flex items-center justify-between">
          <span>Policy Editor</span>
          <div class="flex gap-2">
            <button class="btn-secondary text-xs" @click="loadDefaultPolicy">
              Load Default
            </button>
            <button class="btn-secondary text-xs" @click="parseYaml">
              Validate
            </button>
            <button
              class="btn-primary text-xs"
              :disabled="saving"
              @click="savePolicy"
            >
              {{ saving ? "Saving..." : "Save" }}
            </button>
          </div>
        </div>
        <div class="card-body">
          <textarea
            v-model="policyYaml"
            class="w-full h-96 font-mono text-sm p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-guard-500 focus:border-transparent"
            spellcheck="false"
            placeholder="Enter your policy YAML here..."
          ></textarea>

          <!-- 状态消息 -->
          <div class="mt-3 space-y-1">
            <p v-if="parseError" class="text-red-500 text-sm">
              {{ parseError }}
            </p>
            <p v-if="saveMessage" class="text-green-600 text-sm">
              {{ saveMessage }}
            </p>
            <p
              v-if="rulesLoaded !== null && !saveMessage"
              class="text-gray-400 text-sm"
            >
              {{ rulesLoaded }} rules active
            </p>
          </div>
        </div>
      </div>

      <!-- 侧边栏 -->
      <div class="space-y-6">
        <!-- 解析后的规则列表 -->
        <div class="card">
          <div class="card-header">
            Rules ({{ parsedRules.length }})
          </div>
          <div class="card-body space-y-3 max-h-80 overflow-y-auto">
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

        <!-- 模板策略 -->
        <div class="card">
          <div class="card-header">Templates</div>
          <div class="card-body space-y-2">
            <button
              v-for="tmpl in examplePolicies"
              :key="tmpl.file"
              class="w-full text-left px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
              @click="loadExample(tmpl.name)"
            >
              {{ tmpl.name }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 自定义意图管理 -->
    <div class="card mt-6">
      <div class="card-header">Custom Intents</div>
      <div class="card-body">
        <p class="text-sm text-gray-500 mb-4">
          Define custom detection intents for the semantic layer.
        </p>

        <!-- 意图添加表单 -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          <!-- Name -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Name
            </label>
            <input
              v-model="intentForm.name"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
              placeholder="e.g. block-pii-leak"
            />
          </div>

          <!-- Category -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Category
            </label>
            <select
              v-model="intentForm.category"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
            >
              <option value="security">Security</option>
              <option value="data_access">Data Access</option>
              <option value="system">System</option>
              <option value="resource">Resource</option>
            </select>
          </div>

          <!-- Severity -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Severity
            </label>
            <select
              v-model="intentForm.severity"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
            >
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          <!-- Patterns -->
          <div class="md:col-span-2">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Patterns
            </label>
            <input
              v-model="intentForm.patterns"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
              placeholder="Comma-separated patterns, e.g. SSN, credit card, password"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <input
              v-model="intentForm.description"
              type="text"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-guard-500"
              placeholder="Optional description"
            />
          </div>
        </div>

        <div class="flex items-center gap-3">
          <button
            class="btn-primary text-sm"
            :disabled="addingIntent || !intentForm.name.trim()"
            @click="handleAddIntent"
          >
            {{ addingIntent ? "Adding..." : "Add Intent" }}
          </button>
          <span v-if="intentMessage" class="text-sm" :class="intentMessage.includes('success') ? 'text-green-600' : 'text-red-500'">
            {{ intentMessage }}
          </span>
        </div>

        <!-- 已添加的意图列表 -->
        <div v-if="customIntents.length > 0" class="mt-6">
          <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
            Added Intents ({{ customIntents.length }})
          </p>
          <div class="space-y-2">
            <div
              v-for="(intent, idx) in customIntents"
              :key="intent.name"
              class="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-sm text-gray-800">
                    {{ intent.name }}
                  </span>
                  <span
                    class="text-xs px-2 py-0.5 rounded-full font-medium"
                    :class="severityColor(intent.severity)"
                  >
                    {{ intent.severity }}
                  </span>
                  <span class="text-xs text-gray-400">
                    {{ intent.category }}
                  </span>
                </div>
                <p class="text-xs text-gray-400 mt-0.5">
                  {{ intent.patterns.join(", ") }}
                </p>
                <p v-if="intent.description" class="text-xs text-gray-500 mt-0.5">
                  {{ intent.description }}
                </p>
              </div>
              <button
                class="text-gray-400 hover:text-red-500 transition-colors ml-3"
                title="Remove"
                @click="removeIntent(idx)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div
          v-else
          class="mt-4 text-center py-6 text-gray-400 text-sm"
        >
          No custom intents added yet. Use the form above to create one.
        </div>
      </div>
    </div>
  </div>
</template>
