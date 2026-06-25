"""
merger.py — Marker-based README.md section insertion.

Markers look like:
    <!-- AUTO-README:USAGE:START -->
    ...content...
    <!-- AUTO-README:USAGE:END -->

Rules:
- If markers exist: replace ONLY the content between them.
- If markers don't exist: append the section (before ## License if one exists).
- Never touch content outside markers.
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Marker helpers
# ---------------------------------------------------------------------------


def _start_marker(section_id: str) -> str:
    return f"<!-- AUTO-README:{section_id}:START -->"


def _end_marker(section_id: str) -> str:
    return f"<!-- AUTO-README:{section_id}:END -->"


def _wrap_section(content: str, section_id: str) -> str:
    """Wrap content in START/END markers."""
    start = _start_marker(section_id)
    end = _end_marker(section_id)
    # Ensure content ends with a newline
    body = content.rstrip("\n") + "\n"
    return f"{start}\n{body}{end}\n"


# ---------------------------------------------------------------------------
# Read / write README
# ---------------------------------------------------------------------------

def _read_readme(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _find_license_heading(text: str) -> int | None:
    """Return the character offset of a ## License heading, or None.

    Skips matches inside fenced code blocks (``` ... ``` or ~~~ ... ~~~).
    """
    in_code_block = False
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped_line = line.strip()
        if stripped_line.startswith(("```", "~~~")):
            in_code_block = not in_code_block
        elif not in_code_block and re.match(r"^## License\b", stripped_line, re.IGNORECASE):
            return offset
        offset += len(line)
    return None


# ---------------------------------------------------------------------------
# Core merge logic
# ---------------------------------------------------------------------------

def merge_section(
    readme_text: str,
    section_id: str,
    new_content: str,
) -> str:
    """
    Merge new_content into readme_text under the given section_id markers.

    Args:
        readme_text: The full current README content.
        section_id: e.g. "USAGE", "INSTALLATION", "API".
        new_content: The new markdown to write between markers.

    Returns:
        The updated README text. Content outside markers is never modified.
    """
    start_marker = _start_marker(section_id)
    end_marker = _end_marker(section_id)

    # Escape for regex
    start_escaped = re.escape(start_marker)
    end_escaped = re.escape(end_marker)

    pattern = re.compile(
        rf'{start_escaped}.*?{end_escaped}',
        re.DOTALL,
    )

    wrapped = _wrap_section(new_content, section_id)

    if pattern.search(readme_text):
        # Markers exist — replace only the block between them (inclusive)
        return pattern.sub(lambda _: wrapped.strip(), readme_text, count=1)
    else:
        # No markers — insert before ## License or append at end
        license_pos = _find_license_heading(readme_text)
        if license_pos is not None:
            insert_at = license_pos
            before = readme_text[:insert_at].rstrip("\n") + "\n\n"
            after = readme_text[insert_at:]
            return before + wrapped + "\n" + after
        else:
            # Append at end
            if not readme_text.strip():
                return wrapped.rstrip("\n") + "\n"
            tail = readme_text.rstrip("\n")
            return tail + "\n\n" + wrapped


def merge_sections(
    readme_path: str | Path,
    sections: dict[str, str],
    *,
    dry_run: bool = False,
) -> str:
    """
    Apply multiple section merges to a README file.

    Args:
        readme_path: Path to the README.md file.
        sections: Mapping of section_id (e.g. "USAGE") → new markdown content.
        dry_run: If True, return the result without writing to disk.

    Returns:
        The final merged README text.
    """
    path = Path(readme_path)
    text = _read_readme(path)

    for section_id, content in sections.items():
        text = merge_section(text, section_id.upper(), content)

    if not dry_run:
        path.write_text(text, encoding="utf-8")

    return text
