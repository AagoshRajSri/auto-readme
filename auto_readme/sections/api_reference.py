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


_BATCH_SYSTEM = """\
You are an elite technical writer producing premium API reference documentation.
You will receive a list of Python functions and classes from a single module.
For EACH item, write a crisp 1–3 sentence description covering what it does, its key parameters, and return value.
Use the real names exactly as given — do NOT invent parameters or behavior.
Output ONLY a JSON array (no markdown fences) where each element is:
  {"name": "<function_or_class_name>", "doc": "<your markdown description>"}
One element per input item, in the same order.
"""


def _batch_prompt(mod_path: str, fns: list, classes: list) -> str:
    items = []
    for fn in fns:
        entry = f"FUNCTION `{fn.name}{fn.signature}`"
        if fn.docstring:
            entry += f"\nDocstring: {fn.docstring.split(chr(10))[0]}"
        items.append(entry)
    for cls in classes:
        entry = f"CLASS `{cls.name}`"
        if cls.bases:
            entry += f" (bases: {', '.join(cls.bases)})"
        if cls.docstring:
            entry += f"\nDocstring: {cls.docstring.split(chr(10))[0]}"
        if cls.methods:
            sigs = ", ".join(f"`{m.name}{m.signature}`" for m in cls.methods[:5])
            entry += f"\nMethods: {sigs}"
        items.append(entry)
    numbered = "\n\n".join(f"{i+1}. {item}" for i, item in enumerate(items))
    return f"Module: `{mod_path}`\n\nDocument these {len(items)} items:\n\n{numbered}"


def _parse_batch_response(text: str, names: list[str]) -> dict[str, str]:
    """Parse the JSON array response, fall back to empty strings on error."""
    import json, re
    # Strip any accidental markdown fences
    text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(text)
        return {item["name"]: item.get("doc", "") for item in data if "name" in item}
    except Exception:
        # Best-effort: return empty so we fall back to signature-only
        return {}


def build_api_reference(
    result: AnalysisResult,
    *,
    dry_run: bool = False,
    max_tokens_per_symbol: int = 300,
) -> str:
    """
    Build the API Reference section.

    Makes ONE LLM call per module (batching all symbols), not one per symbol.

    Args:
        result: Analyzer output.
        dry_run: If True, skip LLM calls and return placeholder text.
        max_tokens_per_symbol: Token budget per symbol (used to compute batch budget).

    Returns:
        Markdown string for the ## API Reference section (without markers).
    """
    lines: list[str] = ["## API Reference", ""]
    lines.append(
        "> **Note:** This section is generated per-module in a single batched call "
        "to minimise API quota usage."
    )
    lines.append("")

    for mod in result.modules:
        fns = mod.functions
        classes = mod.classes
        if not fns and not classes:
            continue

        lines.append(f"### `{mod.path}`")
        lines.append("")
        if mod.docstring:
            lines.append(mod.docstring)
            lines.append("")

        # Build name → description map via ONE batched LLM call
        docs: dict[str, str] = {}
        if not dry_run and (fns or classes):
            names = [fn.name for fn in fns] + [cls.name for cls in classes]
            batch_max = max_tokens_per_symbol * len(names)
            prompt = _batch_prompt(mod.path, fns, classes)
            try:
                raw = generate(prompt, system=_BATCH_SYSTEM, max_tokens=min(batch_max, 4096))
                docs = _parse_batch_response(raw, names)
            except Exception:
                docs = {}  # fall back gracefully to signature-only output

        # Functions
        for fn in fns:
            lines.append(f"#### `{fn.name}{fn.signature}`")
            lines.append("")
            if dry_run:
                lines.append(f"<!-- DRY RUN: would generate docs for `{fn.name}` -->")
            else:
                lines.append(docs.get(fn.name, "_No description generated._"))
            lines.append("")

        # Classes
        for cls in classes:
            lines.append(f"#### class `{cls.name}`")
            if cls.bases:
                bases_str = ", ".join(f"`{b}`" for b in cls.bases)
                lines.append(f"*Bases: {bases_str}*")
            lines.append("")
            if dry_run:
                lines.append(f"<!-- DRY RUN: would generate docs for class `{cls.name}` -->")
            else:
                lines.append(docs.get(cls.name, "_No description generated._"))
            lines.append("")

            if cls.methods:
                for meth in cls.methods:
                    lines.append(f"- **`{meth.name}{meth.signature}`**")
                    if meth.docstring:
                        first_line = meth.docstring.split("\n")[0].strip()
                        lines.append(f"  {first_line}")
                lines.append("")

    return "\n".join(lines) + "\n"

