/**
 * AgentGuard VS Code Extension — AI output safety in your editor.
 *
 * Detects dangerous LLM output (DROP TABLE, rm -rf, API key leaks, etc.)
 * and highlights them with VS Code diagnostics (red wavy lines).
 *
 * Activation: onStartupFinished — no user action required.
 *
 * Architecture: Extension → HTTP → Python guard daemon (Phase 3a FastAPI)
 *
 * Commands:
 *   - Ctrl+Alt+G V / Right-click → Validate Selection
 *   - AgentGuard: Validate Current File
 *   - AgentGuard: Show Audit Log
 *   - AgentGuard: Clear All Diagnostics
 *
 * Configuration (settings.json):
 *   - agentguard.guardDaemonUrl: URL of the guard daemon (default: http://127.0.0.1:8765)
 *   - agentguard.policyPath: Path to YAML policy file
 *   - agentguard.enableSemantic: Enable semantic checking (default: true)
 *   - agentguard.enableDiagnostics: Show inline diagnostics (default: true)
 *   - agentguard.dangerousIntents: Specific intents to block
 */

import * as vscode from "vscode";
import { GuardConfig, healthCheck } from "./guardClient";
import { GuardDiagnostics } from "./diagnostics";
import { registerCommands } from "./commands";

/**
 * Read extension configuration from VS Code settings.
 */
function getConfig(): GuardConfig {
  const vsConfig = vscode.workspace.getConfiguration("agentguard");

  return {
    guardDaemonUrl: vsConfig.get<string>("guardDaemonUrl", "http://127.0.0.1:8765"),
    policyPath: vsConfig.get<string>("policyPath") || undefined,
    enableSemantic: vsConfig.get<boolean>("enableSemantic", true),
    dangerousIntents: vsConfig.get<string[]>("dangerousIntents", []),
  };
}

/**
 * Activate the AgentGuard extension.
 *
 * @param context - VS Code extension context.
 */
export async function activate(context: vscode.ExtensionContext): Promise<void> {
  console.log("[AgentGuard] Activating extension...");

  const config = getConfig();
  const diagnostics = new GuardDiagnostics(config);

  // Check daemon connectivity
  const daemonAlive = await healthCheck(config);
  if (!daemonAlive) {
    const action = await vscode.window.showWarningMessage(
      `AgentGuard daemon not reachable at ${config.guardDaemonUrl}. ` +
      `Start it with: agentguard-daemon`,
      "Retry",
      "Configure URL"
    );
    if (action === "Retry") {
      // Will be handled by onDidChangeConfiguration
    } else if (action === "Configure URL") {
      vscode.commands.executeCommand(
        "workbench.action.openSettings",
        "agentguard.guardDaemonUrl"
      );
    }
  } else {
    console.log(`[AgentGuard] Daemon connected: ${config.guardDaemonUrl}`);
  }

  // Register diagnostics
  if (config.enableSemantic || config.policyPath) {
    diagnostics.activate(context);
    console.log("[AgentGuard] Diagnostics active");
  } else {
    console.log(
      "[AgentGuard] Diagnostics disabled — enable semantic or set policyPath"
    );
  }

  // Register commands
  registerCommands(context, diagnostics);

  // Listen for config changes
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("agentguard")) {
        const newConfig = getConfig();
        diagnostics.clear();
        if (newConfig.enableSemantic || newConfig.policyPath) {
          diagnostics.activate(context);
        }
        console.log("[AgentGuard] Configuration updated");
      }
    })
  );

  console.log("[AgentGuard] Extension activated successfully");
}

/**
 * Deactivate the AgentGuard extension.
 */
export function deactivate(): void {
  console.log("[AgentGuard] Extension deactivated");
}
