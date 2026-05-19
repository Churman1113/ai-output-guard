/**
 * AgentGuard diagnostics provider for VS Code.
 *
 * Maintains a diagnostic collection for each open text document.
 * On document change, debounces a Guard validation and reports
 * results as VS Code diagnostics (wavy underlines).
 */

import * as vscode from "vscode";
import { validate, GuardConfig, GuardResult } from "./guardClient";

/**
 * Mapping from GuardLevel to VS Code DiagnosticSeverity.
 */
const LEVEL_SEVERITY: Record<string, vscode.DiagnosticSeverity> = {
  deny: vscode.DiagnosticSeverity.Error,
  warn: vscode.DiagnosticSeverity.Warning,
  ask_human: vscode.DiagnosticSeverity.Warning,
  fix: vscode.DiagnosticSeverity.Information,
  pass: vscode.DiagnosticSeverity.Information,
};

/**
 * AgentGuard diagnostics provider.
 *
 * Usage:
 *   const provider = new GuardDiagnostics(context, config);
 *   provider.activate();
 */
export class GuardDiagnostics {
  private _collection: vscode.DiagnosticCollection;
  private _config: GuardConfig;
  private _debounceTimers: Map<string, NodeJS.Timeout> = new Map();
  private _debounceMs: number = 500;

  constructor(config: GuardConfig) {
    this._config = config;
    this._collection = vscode.languages.createDiagnosticCollection("agentguard");
  }

  /**
   * Get the current guard configuration.
   */
  public getConfig(): GuardConfig {
    return this._config;
  }

  /**
   * Activate diagnostics — start listening to document changes.
   */
  public activate(context: vscode.ExtensionContext): void {
    context.subscriptions.push(this._collection);

    // Validate on document save
    context.subscriptions.push(
      vscode.workspace.onDidSaveTextDocument((doc) => {
        this.validateDocument(doc);
      })
    );

    // Validate on document change (debounced)
    context.subscriptions.push(
      vscode.workspace.onDidChangeTextDocument((event) => {
        const uri = event.document.uri.toString();
        const existing = this._debounceTimers.get(uri);
        if (existing) {
          clearTimeout(existing);
        }
        this._debounceTimers.set(
          uri,
          setTimeout(() => {
            this._debounceTimers.delete(uri);
            this.validateDocument(event.document);
          }, this._debounceMs)
        );
      })
    );

    // Validate active editor on startup
    if (vscode.window.activeTextEditor) {
      this.validateDocument(vscode.window.activeTextEditor.document);
    }
  }

  /**
   * Validate a document and update diagnostics.
   */
  public async validateDocument(document: vscode.TextDocument): Promise<void> {
    if (!this._config.enableSemantic && !this._config.policyPath) {
      return; // Guard not enabled
    }

    const text = document.getText();
    if (!text || text.trim().length === 0) {
      this._collection.set(document.uri, []);
      return;
    }

    try {
      const result = await validate(text, this._config);
      this._updateDiagnostics(document, result);
    } catch (err) {
      // CLI not available — skip silently
      console.warn(`[AgentGuard] Validation failed: ${err}`);
    }
  }

  /**
   * Validate a specific text selection.
   */
  public async validateSelection(
    document: vscode.TextDocument,
    selection: vscode.Selection
  ): Promise<GuardResult | null> {
    const text = document.getText(selection);
    if (!text || text.trim().length === 0) {
      return null;
    }

    try {
      const result = await validate(text, this._config);
      this._updateDiagnosticsForRange(document, selection, result);
      return result;
    } catch (err) {
      vscode.window.showErrorMessage(
        `AgentGuard validation failed: ${err}`
      );
      return null;
    }
  }

  /**
   * Clear all diagnostics.
   */
  public clear(): void {
    this._collection.clear();
  }

  /**
   * Dispose the diagnostics provider.
   */
  public dispose(): void {
    this._collection.dispose();
    for (const timer of this._debounceTimers.values()) {
      clearTimeout(timer);
    }
    this._debounceTimers.clear();
  }

  /**
   * Update diagnostics for the entire document.
   */
  private _updateDiagnostics(
    document: vscode.TextDocument,
    result: GuardResult
  ): void {
    const diagnostics: vscode.Diagnostic[] = [];

    for (const check of result.checks) {
      if (check.level === "pass") {
        continue; // No diagnostic for passing checks
      }

      const severity = LEVEL_SEVERITY[check.level] ?? vscode.DiagnosticSeverity.Warning;
      const diagnostic = new vscode.Diagnostic(
        new vscode.Range(0, 0, document.lineCount - 1, 0),
        `[AgentGuard] ${check.message}`,
        severity
      );
      diagnostic.source = "AgentGuard";
      diagnostic.code = check.layer;
      diagnostic.tags = [vscode.DiagnosticTag.Unnecessary];

      diagnostics.push(diagnostic);
    }

    this._collection.set(document.uri, diagnostics);
  }

  /**
   * Update diagnostics for a specific range (selection validation).
   */
  private _updateDiagnosticsForRange(
    document: vscode.TextDocument,
    selection: vscode.Selection,
    result: GuardResult
  ): void {
    const diagnostics: vscode.Diagnostic[] = [];

    for (const check of result.checks) {
      if (check.level === "pass") {
        continue;
      }

      const severity = LEVEL_SEVERITY[check.level] ?? vscode.DiagnosticSeverity.Warning;

      // Create a range from the selection
      const range = new vscode.Range(
        selection.start.line,
        selection.start.character,
        selection.end.line,
        selection.end.character
      );

      const diagnostic = new vscode.Diagnostic(
        range,
        `[AgentGuard] ${check.message}`,
        severity
      );
      diagnostic.source = "AgentGuard";
      diagnostic.code = check.layer;
      diagnostic.tags = [vscode.DiagnosticTag.Unnecessary];

      diagnostics.push(diagnostic);
    }

    this._collection.set(document.uri, diagnostics);
  }
}
