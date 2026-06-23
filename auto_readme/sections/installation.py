"""
sections/installation.py — Template-driven Installation section.

No LLM call needed — the manifest data is already structured.
"""

from __future__ import annotations

from auto_readme.manifest import ProjectManifest

_MARKER_START = "<!-- AUTO-README:INSTALLATION:START -->"
_MARKER_END = "<!-- AUTO-README:INSTALLATION:END -->"


def build_installation(manifest: ProjectManifest) -> str:
    """
    Build the Installation section from manifest data only.

    No LLM call — the data is structured and doesn't need prose generation.
    Returns the raw markdown content (without markers).
    """
    lines: list[str] = ["## Installation"]
    lines.append("")

    if manifest.python_requires:
        lines.append(f"Requires Python **{manifest.python_requires}**.")
        lines.append("")

    if manifest.is_published:
        lines.append("Install from PyPI:")
        lines.append("")
        lines.append("```bash")
        lines.append(f"pip install {manifest.name}")
        lines.append("```")
    else:
        lines.append("Clone the repository and install in editable mode:")
        lines.append("")
        lines.append("```bash")
        lines.append("git clone <repo-url>")
        lines.append(f"cd {manifest.name}")
        lines.append("pip install -e .")
        lines.append("```")

    if manifest.dependencies:
        lines.append("")
        lines.append("**Runtime dependencies** (installed automatically):")
        lines.append("")
        for dep in manifest.dependencies:
            lines.append(f"- `{dep}`")

    if manifest.cli_scripts:
        lines.append("")
        lines.append("**CLI commands available after install:**")
        lines.append("")
        for script_name in manifest.cli_scripts:
            lines.append(f"- `{script_name}`")

    lines.append("")
    return "\n".join(lines)
