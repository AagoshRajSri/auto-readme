"""
sections/usage.py — LLM-generated Usage section.

Input: detected entry points + their signature/docstring from the analyzer.
One scoped LLM prompt per entry point — NOT the whole file.
"""

from __future__ import annotations

from auto_readme.analyzer import AnalysisResult, FunctionInfo
from auto_readme.llm import generate
from auto_readme.manifest import ProjectManifest

_SYSTEM_PROMPT = """\
You are a world-class technical writer producing stunning, beautifully structured Usage documentation for elite developer READMEs.
Your output is read by developers evaluating whether to adopt a project — make them feel the product is powerful and polished.

Rules:
- Use the REAL function/class/argument names from the provided signature. Do NOT invent any names.
- Structure: a 1-2 sentence engaging intro paragraph, then a well-commented code block, then optionally 1-2 short bullet points for key options/flags.
- Code blocks must have meaningful inline comments explaining what each step does.
- Use markdown callouts (> [!TIP] or > [!NOTE]) where appropriate to highlight key behaviours.
- Output beautifully formatted markdown only. Do NOT add a top-level `## Usage` heading — the caller adds it.
- Keep it concise and impactful: quality over length.
"""


def _format_function_context(fn: FunctionInfo) -> str:
    """Format a tight context block for a single entry-point function."""
    parts: list[str] = []
    parts.append(f"Function: `{fn.name}`")
    parts.append(f"Signature: `{fn.name}{fn.signature}`")
    parts.append(f"File: `{fn.file_path}` (line {fn.line_number})")
    if fn.docstring:
        parts.append(f"\nDocstring:\n{fn.docstring}")
    else:
        parts.append("\n(No docstring available.)")
    return "\n".join(parts)


def _collect_entry_point_functions(result: AnalysisResult) -> list[FunctionInfo]:
    """Return candidate entry-point functions from the codebase.

    Priority order:
    1. All public functions from modules that contain a __main__ block.
    2. Additionally, functions named 'main', 'app', 'run', or 'cli' from any module,
       so long as they aren't already included.
    """
    entry_files = {ep["file"] for ep in result.entry_points if ep.get("type") == "main_block"}

    seen_names: set[str] = set()
    candidates: list[FunctionInfo] = []

    # Priority 1: all functions from __main__ modules
    for mod in result.modules:
        if mod.path in entry_files:
            for fn in mod.functions:
                candidates.append(fn)
                seen_names.add(fn.name)

    # Priority 2: named entry-point-like functions from any module
    for mod in result.modules:
        for fn in mod.functions:
            if fn.name in ("main", "app", "run", "cli") and fn.name not in seen_names:
                candidates.append(fn)
                seen_names.add(fn.name)

    return candidates


def build_usage(
    result: AnalysisResult,
    manifest: ProjectManifest,
    *,
    dry_run: bool = False,
) -> str:
    """
    Build the Usage section using a scoped LLM prompt per entry point.

    Args:
        result: Analyzer output.
        manifest: Project manifest (for CLI script names).
        dry_run: If True, skip LLM calls and return a placeholder.

    Returns:
        Markdown string for the Usage section (without wrapping markers).
    """
    lines: list[str] = ["## Usage", ""]

    # CLI scripts from manifest
    if manifest.cli_scripts:
        lines.append("### CLI")
        lines.append("")
        for script_name, entrypoint in manifest.cli_scripts.items():
            lines.append(f"After installation, the `{script_name}` command is available:")
            lines.append("")
            lines.append("```bash")
            lines.append(f"{script_name} --help")
            lines.append("```")
            lines.append("")

    # Entry point functions — one LLM call each
    fns = _collect_entry_point_functions(result)
    if fns:
        lines.append("### Programmatic Usage")
        lines.append("")
        capped = fns[:3]
        if len(fns) > 3:
            skipped = len(fns) - 3
            lines.append(f"> **Note:** {skipped} additional entry point(s) were detected but omitted to keep costs manageable. Use `--dry-run` to preview all.")
            lines.append("")
        for fn in capped:
            if dry_run:
                lines.append(f"<!-- DRY RUN: would generate usage for `{fn.name}` -->")
                lines.append("")
                continue

            context = _format_function_context(fn)
            prompt = (
                f"Write a Usage subsection for the following Python entry point.\n\n"
                f"{context}\n\n"
                f"Show how a developer would call or invoke this from the command line or Python."
            )
            generated = generate(prompt, system=_SYSTEM_PROMPT, max_tokens=512)
            lines.append(generated.strip())
            lines.append("")

    if not manifest.cli_scripts and not fns:
        if dry_run:
            lines.append("<!-- DRY RUN: no entry points detected -->")
        elif manifest.description:
            valid_symbols = list(result.all_symbol_names)[:15]
            suggestion = f" Use these real symbols from the codebase if possible: {', '.join(valid_symbols)}." if valid_symbols else ""
            
            # Generic usage from manifest name
            prompt = (
                f"Write an elegant and beautifully written Usage section for a premium Python package called `{manifest.name}`. "
                f"Description: {manifest.description}\n"
                f"Show a clean, professional import and usage example that wows the reader.{suggestion} "
                f"CRITICAL: DO NOT invent fake function names or classes. Only use standard Python built-ins or the real symbols provided, otherwise validation will fail."
            )
            generated = generate(prompt, system=_SYSTEM_PROMPT, max_tokens=400)
            lines.append(generated.strip())
            lines.append("")
        else:
            lines.append("No entry points or CLI scripts were detected in this project. Install the package and refer to the source code for usage details.")
            lines.append("")

    return "\n".join(lines) + "\n"
