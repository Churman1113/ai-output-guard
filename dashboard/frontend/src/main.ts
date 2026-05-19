import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { createPinia } from "pinia";
import App from "./App.vue";
import "./assets/main.css";

// Views
import DashboardView from "./views/Dashboard.vue";
import AuditLogView from "./views/AuditLog.vue";
import PoliciesView from "./views/Policies.vue";
import SettingsView from "./views/Settings.vue";

const routes = [
  { path: "/", component: DashboardView, meta: { title: "Dashboard" } },
  { path: "/audit", component: AuditLogView, meta: { title: "Audit Log" } },
  { path: "/policies", component: PoliciesView, meta: { title: "Policies" } },
  { path: "/settings", component: SettingsView, meta: { title: "Settings" } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

const pinia = createPinia();
const app = createApp(App);

app.use(router);
app.use(pinia);
app.mount("#app");
