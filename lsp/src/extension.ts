/**
 * AI Output Guard VS Code Extension — AI output safety in your editor.
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
 *   - AI Output Guard: Validate Current File
 *   - AI Output Guard: Show Audit Log
 *   - AI Output Guard: Clear All Diagnostics
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
 * Activate the AI Output Guard extension.
 *
 * @param context - VS Code extension context.
 */
export async function activate(context: vscode.ExtensionContext): Promise<void> {
  console.log("[AI Output Guard] Activating extension...");

  const config = getConfig();
  const diagnostics = new GuardDiagnostics(config);

  // Check daemon connectivity
  const daemonAlive = await healthCheck(config);
  if (!daemonAlive) {
    const action = await vscode.window.showWarningMessage(
      `AI Output Guard daemon not reachable at ${config.guardDaemonUrl}. ` +
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
    console.log(`[AI Output Guard] Daemon connected: ${config.guardDaemonUrl}`);
  }

  // Register diagnostics
  if (config.enableSemantic || config.policyPath) {
    diagnostics.activate(context);
    console.log("[AI Output Guard] Diagnostics active");
  } else {
    console.log(
      "[AI Output Guard] Diagnostics disabled — enable semantic or set policyPath"
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
        console.log("[AI Output Guard] Configuration updated");
      }
    })
  );

  console.log("[AI Output Guard] Extension activated successfully");
}

/**
 * Deactivate the AI Output Guard extension.
 */
export function deactivate(): void {
  console.log("[AI Output Guard] Extension deactivated");
}
