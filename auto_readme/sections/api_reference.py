"""
sections/api_reference.py — LLM-generated API Reference section.

One LLM call per public symbol (function or class).
This is intentionally the most expensive part — see docstring warning below.

WARNING: Running this against a large codebase (100+ symbols) will make
many API calls and incur real cost. Use --section usage only for quick runs,
or add caching (see Stretch scope in the project brief).
"""

from __future__ import annotations

from auto_readme.analyzer import AnalysisResult, ClassInfo, FunctionInfo
from auto_readme.llm import generate

_FUNCTION_SYSTEM = """\
You are an elite technical writer producing premium, beautifully written API reference documentation.
You will receive the signature and docstring of a single Python function.
Write a highly polished, engaging, and crisp reference entry (2–5 sentences) describing what it does, its parameters, and its return value. Ensure the tone is welcoming and exceptionally professional.
Use the real names — do not invent parameters or behavior not present in the signature or docstring.
Output only the beautiful markdown description text, no headings. Use parameter names in backticks when referencing them.
"""

_CLASS_SYSTEM = """\
You are an elite technical writer producing premium, beautifully written API reference documentation.
You will receive the name, bases, docstring, and public method signatures of a single Python class.
Write a highly polished, engaging, and professional reference entry describing the class purpose, its constructor (if methods include __init__), and its key public methods.
Ensure the text flows beautifully and provides exceptional clarity to developers reading it.
Do not invent behavior not described in the signatures or docstring.
Output only the beautiful markdown description text, no headings.
"""


def _function_prompt(fn: FunctionInfo) -> str:
    parts = [
        f"Function: `{fn.name}`",
        f"Signature: `{fn.name}{fn.signature}`",
        f"File: `{fn.file_path}` (line {fn.line_number})",
    ]
    if fn.is_async:
        parts.append("(async function)")
    if fn.docstring:
        parts.append(f"\nDocstring:\n{fn.docstring}")
    else:
        parts.append("\n(No docstring available.)")
    return "\n".join(parts)


def _class_prompt(cls: ClassInfo) -> str:
    parts = [f"Class: `{cls.name}`"]
    if cls.bases:
        parts.append(f"Bases: {', '.join(f'`{b}`' for b in cls.bases)}")
    parts.append(f"File: `{cls.file_path}` (line {cls.line_number})")
    if cls.docstring:
        parts.append(f"\nDocstring:\n{cls.docstring}")
    else:
        parts.append("\n(No docstring.)")

    if cls.methods:
        parts.append("\nPublic methods:")
        for m in cls.methods:
            sig_line = f"  - `{m.name}{m.signature}`"
            if m.docstring:
                first_line = m.docstring.split("\n")[0].strip()
                sig_line += f" — {first_line}"
            parts.append(sig_line)

    return "\n".join(parts)


def build_api_reference(
    result: AnalysisResult,
    *,
    dry_run: bool = False,
    max_tokens_per_symbol: int = 300,
) -> str:
    """
    Build the API Reference section.

    Makes one LLM call per public function/class, grouped by module.

    Args:
        result: Analyzer output.
        dry_run: If True, skip LLM calls and return placeholder text.
        max_tokens_per_symbol: Token budget per LLM call.

    Returns:
        Markdown string for the ## API Reference section (without markers).

    WARNING: Cost scales linearly with the number of public symbols.
    Use dry_run=True or --section usage to skip this on large codebases.
    """
    lines: list[str] = ["## API Reference", ""]
    lines.append(
        "> **Note:** This section is generated per-symbol. "
        "On large codebases (100+ public symbols) this makes many LLM calls. "
        "Use `--section usage` to skip this."
    )
    lines.append("")

    for mod in result.modules:
        has_content = bool(mod.functions or mod.classes)
        if not has_content:
            continue

        lines.append(f"### `{mod.path}`")
        lines.append("")
        if mod.docstring:
            lines.append(mod.docstring)
            lines.append("")

        # Functions
        for fn in mod.functions:
            lines.append(f"#### `{fn.name}{fn.signature}`")
            lines.append("")

            if dry_run:
                lines.append(f"<!-- DRY RUN: would generate docs for `{fn.name}` -->")
            else:
                prompt = _function_prompt(fn)
                desc = generate(prompt, system=_FUNCTION_SYSTEM, max_tokens=max_tokens_per_symbol)
                lines.append(desc.strip())

            lines.append("")

        # Classes
        for cls in mod.classes:
            lines.append(f"#### class `{cls.name}`")
            if cls.bases:
                lines.append(f"*Bases: {', '.join(cls.bases)}*")
            lines.append("")

            if dry_run:
                lines.append(f"<!-- DRY RUN: would generate docs for class `{cls.name}` -->")
            else:
                prompt = _class_prompt(cls)
                desc = generate(prompt, system=_CLASS_SYSTEM, max_tokens=max_tokens_per_symbol)
                lines.append(desc.strip())

            lines.append("")

            # Method signatures (always shown, no extra LLM call)
            if cls.methods:
                for meth in cls.methods:
                    lines.append(f"- **`{meth.name}{meth.signature}`**")
                    if meth.docstring:
                        first_line = meth.docstring.split("\n")[0].strip()
                        lines.append(f"  {first_line}")
                lines.append("")

    return "\n".join(lines) + "\n"
