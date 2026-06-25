"""
cli.py — Entry point for the auto-readme CLI.

Commands:
    auto-readme generate --section installation,usage,api --path . [--force] [--dry-run]
    auto-readme analyze --path .   (inspect what was extracted, no LLM)

Pipeline order: manifest → analyzer → sections → validator → merger
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from auto_readme import __version__
from auto_readme.analyzer import analyze
from auto_readme.llm import set_provider
from auto_readme.manifest import read_manifest
from auto_readme.merger import merge_sections
from auto_readme.sections.api_reference import build_api_reference
from auto_readme.sections.installation import build_installation
from auto_readme.sections.usage import build_usage
from auto_readme.validator import validate

app = typer.Typer(
    name="auto-readme",
    help="Generate and maintain README.md sections via static analysis + LLM.",
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"auto-readme [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """auto-readme — README section generator backed by static analysis."""


# ---------------------------------------------------------------------------
# analyze command — no LLM, just inspect what was extracted
# ---------------------------------------------------------------------------

@app.command("analyze")
def cmd_analyze(
    path: Path = typer.Argument(Path("."), help="Path to the Python project."),
) -> None:
    """
    [bold]Analyze[/bold] a Python project and print extracted symbols (no LLM calls).
    """
    root = path.resolve()
    if not root.exists():
        err_console.print(f"[red]Error:[/red] Path '{root}' does not exist.")
        raise typer.Exit(1)

    console.print(f"\n[bold]Analyzing:[/bold] {root}\n")

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as prog:
        prog.add_task("Walking Python files...", total=None)
        result = analyze(root)

    console.print(f"[green]Found {len(result.modules)} module(s)[/green]")
    console.print(f"[green]Found {len(result.entry_points)} entry point(s)[/green]\n")

    for mod in result.modules:
        table = Table(title=f"[bold cyan]{mod.path}[/bold cyan]", show_lines=True)
        table.add_column("Kind", style="yellow", width=10)
        table.add_column("Name", style="bold")
        table.add_column("Signature / Info")

        for fn in mod.functions:
            sig = f"{fn.name}{fn.signature}"
            table.add_row(
                "async fn" if fn.is_async else "function",
                fn.name,
                sig,
            )
        for cls in mod.classes:
            bases = f" ({', '.join(cls.bases)})" if cls.bases else ""
            table.add_row("class", cls.name, f"class {cls.name}{bases}")
            for meth in cls.methods:
                table.add_row("  method", meth.name, f"  .{meth.name}{meth.signature}")

        if mod.functions or mod.classes:
            console.print(table)
            console.print()

    if result.entry_points:
        console.print("[bold]Entry points:[/bold]")
        for ep in result.entry_points:
            console.print(f"  [yellow]{ep['type']}[/yellow] in [cyan]{ep['file']}[/cyan]")
    console.print()


# ---------------------------------------------------------------------------
# generate command — full pipeline
# ---------------------------------------------------------------------------

_VALID_SECTIONS = {"installation", "usage", "api"}


@app.command("generate")
def cmd_generate(
    path: Path = typer.Argument(Path("."), help="Path to the Python project."),
    sections: str = typer.Option(
        "installation,usage,api",
        "--section", "-s",
        help="Comma-separated list of sections to generate: installation, usage, api.",
    ),
    readme: Optional[Path] = typer.Option(
        None, "--readme",
        help="Path to README.md (defaults to <path>/README.md).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Print generated sections without writing to README.md.",
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Write even if the validator reports warnings/errors.",
    ),
    provider: str = typer.Option(
        "gemini", "--provider",
        help="LLM provider: gemini, anthropic, or openai.",
    ),
    model: str = typer.Option(
        "", "--model",
        help="Override the LLM model (e.g. gemini-2.5-flash).",
    ),
) -> None:
    """
    [bold]Generate[/bold] README sections via static analysis + LLM.

    Pipeline: manifest → analyzer → sections → validator → merger

    [dim]Examples:[/dim]
      [cyan]auto-readme generate --path . --section usage --dry-run[/cyan]
      [cyan]auto-readme generate --path . --section installation,usage,api[/cyan]
      [cyan]auto-readme generate --path . --force[/cyan]
    """
    root = path.resolve()
    if not root.exists():
        err_console.print(f"[red]Error:[/red] Path '{root}' does not exist.")
        raise typer.Exit(1)

    readme_path = readme or (root / "README.md")

    # Parse and validate section list
    requested = [s.strip().lower() for s in sections.split(",") if s.strip()]
    invalid = [s for s in requested if s not in _VALID_SECTIONS]
    if invalid:
        err_console.print(f"[red]Unknown section(s): {', '.join(invalid)}[/red]")
        err_console.print(f"Valid sections: {', '.join(sorted(_VALID_SECTIONS))}")
        raise typer.Exit(1)

    # Configure LLM
    try:
        set_provider(provider, model=model)
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold]auto-readme generate[/bold]\n"
            f"  Project: [cyan]{root}[/cyan]\n"
            f"  Sections: [yellow]{', '.join(requested)}[/yellow]\n"
            f"  Provider: [magenta]{provider}[/magenta]\n"
            f"  Mode: {'[yellow]dry-run[/yellow]' if dry_run else '[green]write[/green]'}",
            title="[bold blue]auto-readme[/bold blue]",
            border_style="blue",
        )
    )

    # ── Step 1: Manifest ────────────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as prog:
        t = prog.add_task("Reading project manifest...", total=None)
        manifest = read_manifest(root)
        prog.update(t, description=f"Manifest read from: {Path(manifest.source_file).name}")

    console.print(f"  [green]OK[/green] Manifest: [bold]{manifest.name}[/bold] v{manifest.version}")

    # ── Step 2: Analyzer ────────────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as prog:
        t = prog.add_task("Analyzing codebase...", total=None)
        result = analyze(root)

    symbol_count = len(result.all_symbol_names)
    console.print(
        f"  [green]OK[/green] Analyzer: {len(result.modules)} module(s), "
        f"{symbol_count} public symbol(s), "
        f"{len(result.entry_points)} entry point(s)"
    )

    # ── Step 3: Build sections ──────────────────────────────────────────────
    generated: dict[str, str] = {}

    if "installation" in requested:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as prog:
            prog.add_task("Building Installation section (template)...", total=None)
            content = build_installation(manifest)
        generated["INSTALLATION"] = content
        console.print("  [green]OK[/green] Installation section built (no LLM)")

    if "usage" in requested:
        console.print("  [yellow]RUN[/yellow] Building Usage section (LLM)...")
        content = build_usage(result, manifest, dry_run=dry_run)
        generated["USAGE"] = content
        console.print("  [green]OK[/green] Usage section built")

    if "api" in requested:
        console.print(
            "  [yellow]RUN[/yellow] Building API Reference section "
            f"([bold]{symbol_count}[/bold] symbols — one LLM call each)..."
        )
        content = build_api_reference(result, dry_run=dry_run)
        generated["API"] = content
        console.print("  [green]OK[/green] API Reference section built")

    # ── Step 4: Validate ────────────────────────────────────────────────────
    all_warnings = []
    has_blocking_errors = False

    for section_id, content in generated.items():
        vr = validate(content, result)
        if vr.warnings:
            all_warnings.extend(vr.warnings)
            for w in vr.warnings:
                if w.level == "error":
                    has_blocking_errors = True
                    err_console.print(f"  [red bold]FAIL[/red bold] [{section_id}] {w}")
                else:
                    console.print(f"  [yellow]WARN[/yellow]  [{section_id}] {w}")
        else:
            console.print(f"  [green]OK[/green] Validator: {section_id} — no issues")

    if all_warnings:
        console.print(
            f"\n[yellow]Validator found {len(all_warnings)} warning(s).[/yellow]"
        )
        if has_blocking_errors and not force:
            err_console.print(
                "\n[red bold]Blocking errors found. Use --force to write anyway.[/red bold]"
            )
            raise typer.Exit(2)
        elif has_blocking_errors and force:
            console.print("[yellow]--force set: proceeding despite errors.[/yellow]")

    # ── Step 5: Dry-run output or merge ─────────────────────────────────────
    if dry_run:
        console.print("\n[bold yellow]--- DRY RUN OUTPUT ------------------------------[/bold yellow]")
        for section_id, content in generated.items():
            console.print(f"\n[bold cyan]=== {section_id} ===[/bold cyan]")
            console.print(content)
        console.print("[bold yellow]--- END DRY RUN ---------------------------------[/bold yellow]\n")
        console.print("[dim]No files were modified (dry-run).[/dim]")
    else:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as prog:
            prog.add_task(f"Writing {readme_path}...", total=None)
            merge_sections(readme_path, generated)

        console.print(f"\n  [green bold]OK Written:[/green bold] [cyan]{readme_path}[/cyan]")

    console.print("\n[bold green]Done.[/bold green]\n")


if __name__ == "__main__":
    app()
