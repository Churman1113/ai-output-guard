/**
 * AgentGuard VS Code extension commands.
 *
 * Provides commands for manual validation, audit log viewing, and configuration.
 * Communicates with the Python guard daemon (Phase 3a) over HTTP.
 */

import * as vscode from "vscode";
import { GuardDiagnostics } from "./diagnostics";
import { fetchAudit, fetchStatus } from "./guardClient";

/**
 * Register all AgentGuard extension commands.
 *
 * @param context - VS Code extension context.
 * @param diagnostics - Guard diagnostics provider.
 */
export function registerCommands(
  context: vscode.ExtensionContext,
  diagnostics: GuardDiagnostics
): void {
  // ── Validate Selection ──
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "agentguard.validateSelection",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          vscode.window.showInformationMessage(
            "AgentGuard: No active editor to validate"
          );
          return;
        }

        const selection = editor.selection;
        if (selection.isEmpty) {
          vscode.window.showInformationMessage(
            "AgentGuard: Select some text to validate"
          );
          return;
        }

        const result = await diagnostics.validateSelection(
          editor.document,
          selection
        );

        if (result) {
          if (result.passed) {
            vscode.window.showInformationMessage(
              `AgentGuard: Output passed all safety checks (${result.latency_ms.toFixed(1)}ms)`
            );
          } else if (result.blocked) {
            vscode.window.showWarningMessage(
              `AgentGuard: Output blocked by ${result.blocked_by} layer`
            );
          } else if (result.level === "fix") {
            vscode.window.showInformationMessage(
              `AgentGuard: Output was auto-fixed (${result.latency_ms.toFixed(1)}ms)`
            );
          } else {
            vscode.window.showWarningMessage(
              `AgentGuard: ${result.level} — ${result.checks.map((c) => c.message).join("; ")}`
            );
          }
        }
      }
    )
  );

  // ── Validate File ──
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "agentguard.validateFile",
      async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
          vscode.window.showInformationMessage(
            "AgentGuard: No active file to validate"
          );
          return;
        }

        await diagnostics.validateDocument(editor.document);
        vscode.window.showInformationMessage(
          "AgentGuard: File validation complete — check Problems panel for results"
        );
      }
    )
  );

  // ── Show Audit Log ──
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "agentguard.showAudit",
      async () => {
        const panel = vscode.window.createOutputChannel("AgentGuard Audit");
        panel.clear();
        panel.appendLine("AgentGuard Audit Log");
        panel.appendLine("═".repeat(50) + "\n");

        try {
          const audit = await fetchAudit(diagnostics.getConfig(), 50);
          const status = await fetchStatus(diagnostics.getConfig());

          panel.appendLine(`Total events: ${audit.total} | Showing: ${audit.shown}\n`);

          for (const entry of audit.entries) {
            const date = new Date(entry.timestamp * 1000).toISOString();
            const levelIcon = entry.result === "pass" ? "✅" :
                              entry.result === "deny" ? "🛑" :
                              entry.result === "warn" ? "⚠️" : "🔧";

            panel.appendLine(`${levelIcon} [${date}] ${entry.result.toUpperCase()}`);
            panel.appendLine(`   Input:  "${entry.input_preview.substring(0, 80)}"`);
            panel.appendLine(`   Output: "${entry.output_preview.substring(0, 80)}"`);

            if (entry.blocked_by) {
              panel.appendLine(`   Blocked by: ${entry.blocked_by}`);
            }

            for (const check of entry.checks) {
              const checkIcon = check.level === "pass" ? "  ✓" : "  ✗";
              panel.appendLine(`${checkIcon} ${check.layer}: ${check.message}`);
            }
            panel.appendLine("");
          }

          if (status.policy) {
            panel.appendLine("─".repeat(50));
            panel.appendLine(`Policy: ${status.policy.rules} rules active`);
          }
        } catch (err) {
          panel.appendLine(`Failed to fetch audit log: ${err}`);
          panel.appendLine("");
          panel.appendLine("Make sure the AgentGuard daemon is running:");
          panel.appendLine("  $ agentguard-daemon");
        }

        panel.show();
      }
    )
  );

  // ── Clear Diagnostics ──
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "agentguard.clearDiagnostics",
      () => {
        diagnostics.clear();
        vscode.window.showInformationMessage(
          "AgentGuard: Diagnostics cleared"
        );
      }
    )
  );
}
