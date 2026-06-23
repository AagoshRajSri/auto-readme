"""
manifest.py — Read project metadata from pyproject.toml, setup.py, or requirements.txt.

Feeds Installation section directly — no LLM needed here, data is structured.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class ProjectManifest:
    name: str = "unknown"
    version: str = "0.0.0"
    description: str = ""
    python_requires: str = ""
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    cli_scripts: dict[str, str] = field(default_factory=dict)   # name -> entrypoint
    is_published: bool = False     # True if version != "0.0.0" and no "dev"/"alpha" flags
    source_file: str = ""          # which file the metadata was read from

    @property
    def install_command(self) -> str:
        """Return the recommended install command."""
        if self.is_published:
            return f"pip install {self.name}"
        return "pip install -e ."


# ---------------------------------------------------------------------------
# pyproject.toml reader
# ---------------------------------------------------------------------------

def _read_pyproject(path: Path) -> ProjectManifest:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    project = data.get("project", {})
    name = project.get("name", "unknown")
    version = project.get("version", "0.0.0")
    description = project.get("description", "")
    python_requires = project.get("requires-python", "")
    dependencies = project.get("dependencies", [])

    # Optional dev deps under [project.optional-dependencies]
    opt_deps = project.get("optional-dependencies", {})
    dev_deps: list[str] = []
    for key in ("dev", "test", "tests", "lint", "ci"):
        dev_deps.extend(opt_deps.get(key, []))

    # CLI scripts
    cli_scripts: dict[str, str] = {}
    scripts = project.get("scripts", {})
    cli_scripts.update(scripts)

    # Also check [tool.poetry.scripts] for poetry-based projects
    tool = data.get("tool", {})
    poetry = tool.get("poetry", {})
    if "scripts" in poetry:
        cli_scripts.update(poetry["scripts"])

    is_published = bool(
        version
        and version != "0.0.0"
        and not any(tag in version for tag in ("dev", "a", "b", "rc", "alpha", "beta"))
    )

    return ProjectManifest(
        name=name,
        version=version,
        description=description,
        python_requires=python_requires,
        dependencies=dependencies,
        dev_dependencies=dev_deps,
        cli_scripts=cli_scripts,
        is_published=is_published,
        source_file=str(path),
    )


# ---------------------------------------------------------------------------
# requirements.txt fallback
# ---------------------------------------------------------------------------

def _read_requirements(path: Path) -> list[str]:
    deps: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            deps.append(line)
    return deps


# ---------------------------------------------------------------------------
# setup.py helpers
# ---------------------------------------------------------------------------

def _split_install_requires(raw: str) -> list[str]:
    """Split an install_requires list string on dep boundaries.

    Handles version specifiers that contain commas (e.g. ``>=2.28,<3.0``)
    by only splitting on commas that separate quoted strings (i.e. between
    one dependency's closing quote and the next dep's opening quote).
    """
    deps: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    for ch in raw:
        if ch in ("'", '"') and in_quote is None:
            in_quote = ch
            current.append(ch)
        elif ch == in_quote:
            in_quote = None
            current.append(ch)
        elif ch == "," and in_quote is None:
            # Comma outside quotes = separator between dep entries
            piece = "".join(current).strip()
            if piece:
                deps.append(piece)
            current = []
        else:
            current.append(ch)
    piece = "".join(current).strip()
    if piece:
        deps.append(piece)
    return deps


# ---------------------------------------------------------------------------
# setup.py fallback (regex-based, handles simple cases)
# ---------------------------------------------------------------------------

def _read_setup_py(path: Path) -> ProjectManifest:
    source = path.read_text(encoding="utf-8")
    manifest = ProjectManifest(source_file=str(path))

    def _extract(pattern: str) -> str | None:
        m = re.search(pattern, source, re.DOTALL)
        return m.group(1).strip().strip("'\"") if m else None

    name = _extract(r'name\s*=\s*["\']([^"\']+)["\']')
    if name:
        manifest.name = name

    version = _extract(r'version\s*=\s*["\']([^"\']+)["\']')
    if version:
        manifest.version = version

    desc = _extract(r'description\s*=\s*["\']([^"\']+)["\']')
    if desc:
        manifest.description = desc

    # install_requires list — split on commas but respect version specifiers
    ir_match = re.search(r'install_requires\s*=\s*\[([^\]]+)\]', source, re.DOTALL)
    if ir_match:
        raw = ir_match.group(1)
        # Split on comma, but be careful not to split version specifiers like ">=2.28,<3.0"
        # Strategy: split on comma at the top level (not inside quotes/parens)
        deps_raw = _split_install_requires(raw)
        deps = [d.strip().strip("'\"") for d in deps_raw if d and d.strip().strip("'\"")]
        manifest.dependencies = [d for d in deps if d and " " not in d.strip()]

    return manifest


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_manifest(project_root: str | Path) -> ProjectManifest:
    """
    Read project metadata from the best available source under project_root.

    Priority: pyproject.toml → setup.py → requirements.txt (bare fallback).
    """
    root = Path(project_root).resolve()

    pyproject_path = root / "pyproject.toml"
    if pyproject_path.exists():
        manifest = _read_pyproject(pyproject_path)
    else:
        setup_path = root / "setup.py"
        if setup_path.exists():
            manifest = _read_setup_py(setup_path)
        else:
            manifest = ProjectManifest(source_file="<none>")

    # If there is a requirements.txt, merge deps (de-dup)
    req_path = root / "requirements.txt"
    if req_path.exists():
        extra = _read_requirements(req_path)
        existing = set(manifest.dependencies)
        manifest.dependencies.extend(d for d in extra if d not in existing)

    return manifest
