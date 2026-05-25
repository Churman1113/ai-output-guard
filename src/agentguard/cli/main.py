"""AI Output Guard CLI — command-line interface for guard validation.

Usage:
    agentguard check '{"action": "DROP TABLE users"}'
    agentguard validate response.json --policy prod.yaml
    agentguard policy validate policies/prod.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="agentguard",
    help="AI Output Safety Engine — the seatbelt between LLMs and your systems",
    no_args_is_help=True,
)

check_app = typer.Typer(help="Check a single output against the guard")
app.add_typer(check_app, name="check")

validate_app = typer.Typer(help="Validate a file or output against the guard")
app.add_typer(validate_app, name="validate")

policy_app = typer.Typer(help="Policy file management")
app.add_typer(policy_app, name="policy")


def _print_result(result, verbose: bool = False):
    """Pretty-print a GuardResult with colors."""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    level_colors = {
        "pass": "green",
        "warn": "yellow",
        "fix": "blue",
        "ask_human": "magenta",
        "deny": "red",
    }

    color = level_colors.get(result.level.value, "white")

    # Result banner
    console.print(Panel(
        Text(f"  {result.level.value.upper()}  ", style=f"bold white on {color}"),
        title="AI Output Guard Result",
        subtitle=f"latency: {result.metadata.get('latency_ms', 0)}ms",
    ))

    if result.blocked_by:
        console.print(f"[bold]Blocked by:[/] {result.blocked_by}")

    # Checks table
    if verbose or result.checks:
        table = Table(title="Guard Checks")
        table.add_column("Layer", style="cyan")
        table.add_column("Level", style="bold")
        table.add_column("Message")
        table.add_column("Confidence")

        for check in result.checks:
            lvl_color = level_colors.get(check.level.value, "white")
            table.add_row(
                check.layer,
                f"[{lvl_color}]{check.level.value.upper()}[/]",
                check.message,
                f"{check.confidence:.0%}",
            )

        console.print(table)

    return 0 if result.passed else 1


@check_app.command("output")
def check_output(
    content: str = typer.Argument(..., help="Content to validate (JSON string)"),
    schema: Optional[str] = typer.Option(None, "--schema", help="Pydantic model path (module.Class)"),
    semantic: bool = typer.Option(False, "--semantic", help="Enable semantic guard"),
    policy: Optional[str] = typer.Option(None, "--policy", help="Policy file path"),
    intent: Optional[list[str]] = typer.Option(None, "--intent", help="Specific intents to block"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed checks"),
):
    """Validate a single output string."""
    from agentguard import Guard

    schema_obj = None
    if schema:
        # Dynamic import: "myapp.models.APIResponse"
        parts = schema.rsplit(".", 1)
        if len(parts) == 2:
            mod = __import__(parts[0], fromlist=[parts[1]])
            schema_obj = getattr(mod, parts[1])

    guard = Guard(
        schema=schema_obj,
        semantic=semantic,
        dangerous_intents=intent,
        policy=policy,
    )

    result = guard.validate(content)
    sys.exit(_print_result(result, verbose=verbose))


@validate_app.command("file")
def validate_file(
    file: Path = typer.Argument(..., help="JSON file to validate"),
    policy: Optional[str] = typer.Option(None, "--policy", help="Policy file path"),
    semantic: bool = typer.Option(False, "--semantic", help="Enable semantic guard"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed checks"),
):
    """Validate a JSON file."""
    from agentguard import Guard

    content = file.read_text(encoding="utf-8")

    guard = Guard(
        semantic=semantic,
        policy=policy,
    )

    result = guard.validate(content)
    sys.exit(_print_result(result, verbose=verbose))


@policy_app.command("validate")
def policy_validate(
    file: Path = typer.Argument(..., help="Policy YAML file to validate"),
):
    """Validate a policy YAML file."""
    from agentguard.policy.parser import parse_policy_file
    from agentguard.policy.validator import validate_policy
    import yaml
    from rich.console import Console

    console = Console()

    try:
        content = file.read_text(encoding="utf-8")
        raw = yaml.safe_load(content)
        errors = validate_policy(raw)

        if errors:
            console.print("[red bold]Policy validation FAILED:[/]")
            for err in errors:
                console.print(f"  [red]•[/] {err}")
            sys.exit(1)
        else:
            policy = parse_policy_file(file)
            console.print(f"[green bold]Policy '{file}' is valid[/]")
            console.print(f"  Rules: {len(policy.rules)}")
            console.print(f"  Defaults: {policy.defaults}")
            for rule in policy.rules:
                console.print(f"  - [{rule.action}] {rule.name} (priority: {rule.priority})")
            sys.exit(0)

    except Exception as e:
        console.print(f"[red bold]Error:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()
