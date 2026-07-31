"""
validator.py — Hallucination check + markdown linting for generated content.

Three checks:
1. Symbol check: every backtick-quoted `identifier()` or `ClassName` in the
   generated text must exist in the analyzer's known symbol set. Flags mismatches.
2. Markdown linting: heading structure, no broken local file links.
3. Code block syntax: any ```python fenced block is ast.parsed (syntax only, not executed).

On any warning, the caller should print them and require --force to proceed.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auto_readme.analyzer import AnalysisResult

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ValidationWarning:
    level: str          # "error" | "warning"
    check: str          # "symbol", "markdown", "syntax"
    message: str
    line_number: int | None = None

    def __str__(self) -> str:
        loc = f" (line {self.line_number})" if self.line_number is not None else ""
        return f"[{self.level.upper()}:{self.check}]{loc} {self.message}"


@dataclass
class ValidationResult:
    warnings: list[ValidationWarning] = field(default_factory=list)
    text: str = ""          # The original text, unchanged

    @property
    def has_errors(self) -> bool:
        return any(w.level == "error" for w in self.warnings)

    @property
    def ok(self) -> bool:
        return len(self.warnings) == 0


# ---------------------------------------------------------------------------
# Check 1: Symbol hallucination check
# ---------------------------------------------------------------------------

# Matches:
#   `function_name(...)` or `function_name()` → captures "function_name"
#   `ClassName` (PascalCase, no parens)         → captures "ClassName"
#   `module.function` or `Class.method`         → captures both parts
_BACKTICK_PATTERN = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*(?:\([^`]*\))?)`")

# Common English prose words that may appear in backtick-quoted documentation
# text but are NOT code symbols. Without this, the hallucination checker would
# flag "function", "parameter", "returns", etc. as hallucinations.
_PROSE_SKIP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "function", "method", "class", "module", "package", "library",
    "parameter", "argument", "param", "arg", "attribute", "property",
    "returns", "yields", "raises", "type", "value", "key",
    "default", "optional", "required", "config", "setting",
    "string", "number", "integer", "boolean", "dictionary",
    "tuple", "set", "dict", "list", "object",
    "example", "usage", "note", "warning", "tip", "info", "see",
    "file", "path", "dir", "directory", "folder",
    "source", "target", "destination", "output", "input",
    "name", "title", "label", "description", "summary",
    "help", "about", "home", "index", "page", "link",
    "error", "exception", "message", "code", "data",
    "format", "mode", "flag", "option", "command",
    "base", "root", "child", "parent", "item", "element",
    "size", "count", "total", "max", "min", "limit",
    "start", "end", "begin", "finish", "stop",
    "create", "read", "update", "delete",
    "add", "remove", "get", "set", "find", "search",
    "open", "close", "save", "load", "export", "import",
    "init", "reset", "clear", "copy", "move",
    "enable", "disable", "allow", "deny",
    "before", "after", "during", "while", "until",
    "access", "status", "state", "action", "event",
    "simple", "complex", "basic", "advanced",
    "single", "multiple", "many", "several",
    "first", "second", "last", "next", "previous",
    "left", "right", "top", "bottom", "middle",
    "up", "down", "in", "out", "on", "off",
    "yes", "no", "true", "false", "ok",
    "version", "release", "stable", "latest",
    "main", "master", "develop", "feature",
}

# Identifiers that are Python builtins or common non-project names — skip checking
_STDLIB_SKIP = {
    "None", "True", "False", "str", "int", "float", "bool", "list", "dict",
    "set", "tuple", "bytes", "object", "type", "Exception", "ValueError",
    "TypeError", "RuntimeError", "KeyError", "AttributeError", "print",
    "len", "range", "open", "Path", "os", "sys", "re", "ast", "json",
    "Optional", "Union", "Any", "List", "Dict", "Tuple", "Set",
    "TypedDict", "OrderedDict",
    "Callable", "Generator", "Iterator", "Sequence", "Mapping", "Iterable",
    "AsyncIterator", "AsyncIterable", "Awaitable", "Coroutine",
    "dataclass", "field", "property", "staticmethod", "classmethod",
    "super", "self", "cls", "args", "kwargs",
    "pip", "pip install", "pytest", "py", "python", "python3", "bash", "sh",
    "ModuleType", "TypeVar", "Generic", "Type",
    "asyncio", "datetime", "types",
    "Literal", "Protocol", "Final", "ClassVar", "Annotated",
    "Self", "Never", "Required", "NotRequired", "Unpack",
    "Override", "Concatenate", "ParamSpec",
    # Public dunder methods (common in docs but not project-specific symbols)
    "__init__", "__new__", "__call__", "__enter__", "__exit__",
    "__str__", "__repr__", "__len__", "__iter__", "__next__",
    "__contains__", "__getitem__", "__setitem__",
}


def _extract_identifiers_from_text(text: str) -> list[tuple[str, int]]:
    """
    Return (identifier, approx_line_number) pairs for all backtick-quoted
    identifiers in the text. Strips trailing () and splits dotted names.
    """
    results: list[tuple[str, int]] = []
    lines = text.split("\n")
    for line_no, line in enumerate(lines, start=1):
        for match in _BACKTICK_PATTERN.finditer(line):
            raw = match.group(1)
            # Strip parens and args: "function(...)" -> "function"
            name = raw.split("(")[0].strip()
            # Handle dotted: "module.function" -> check both parts
            for part in name.split("."):
                part = part.strip()
                if part:
                    results.append((part, line_no))
    return results


def _check_symbols(text: str, known_symbols: set[str]) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []
    identifiers = _extract_identifiers_from_text(text)
    checked: set[str] = set()

    for name, line_no in identifiers:
        if name in checked:
            continue
        checked.add(name)

        if name in _STDLIB_SKIP:
            continue
        # Skip short strings (likely not identifiers)
        if len(name) < 2:
            continue
        # Skip ALL_CAPS (constants/env vars)
        if name.isupper():
            continue
        # Skip known English prose words that might appear in backticks
        # (e.g., "function", "parameter", "returns") — these are not code symbols.
        if name in _PROSE_SKIP:
            continue

        if name not in known_symbols:
            warnings.append(ValidationWarning(
                level="error",
                check="symbol",
                message=(
                    f"Identifier `{name}` mentioned in generated text "
                    f"does not match any known symbol in the codebase. "
                    f"Possible hallucination."
                ),
                line_number=line_no,
            ))

    return warnings


# ---------------------------------------------------------------------------
# Check 2: Markdown linting
# ---------------------------------------------------------------------------

_LOCAL_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\((?!https?://|#)([^)]+)\)')
_HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


def _check_markdown(text: str) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []

    # Check heading sequence: no skipping levels (h2 → h4 is a jump)
    prev_level = 0
    for match in _HEADING_PATTERN.finditer(text):
        level = len(match.group(1))
        line_no = text[:match.start()].count("\n") + 1
        if prev_level > 0 and level > prev_level + 1:
            warnings.append(ValidationWarning(
                level="warning",
                check="markdown",
                message=(
                    f"Heading level jumps from h{prev_level} to h{level} "
                    f"('{match.group(2)}'). Consider using h{prev_level + 1} instead."
                ),
                line_number=line_no,
            ))
        prev_level = level

    # Check local file links don't look obviously broken
    for match in _LOCAL_LINK_PATTERN.finditer(text):
        link_text = match.group(1)
        link_target = match.group(2)
        line_no = text[:match.start()].count("\n") + 1
        # Flag links that look like they should be local files but are suspiciously invented
        stripped = link_target.split("?")[0].split("#")[0]  # remove query/fragment
        if stripped.endswith((".py", ".md", ".rst", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini")):
            warnings.append(ValidationWarning(
                level="warning",
                check="markdown",
                message=(
                    f"Local file link `[{link_text}]({link_target})` in generated text — "
                    f"verify this file actually exists."
                ),
                line_number=line_no,
            ))

    return warnings


# ---------------------------------------------------------------------------
# Check 3: Python code block syntax
# ---------------------------------------------------------------------------

_CODE_BLOCK_PATTERN = re.compile(r'```python\n(.*?)```', re.DOTALL)


def _check_code_blocks(text: str) -> list[ValidationWarning]:
    warnings: list[ValidationWarning] = []

    for match in _CODE_BLOCK_PATTERN.finditer(text):
        code = match.group(1)
        line_no = text[:match.start()].count("\n") + 1
        try:
            ast.parse(code)
        except SyntaxError as exc:
            warnings.append(ValidationWarning(
                level="error",
                check="syntax",
                message=(
                    f"Python code block at line {line_no} has a syntax error: "
                    f"{exc.msg} (at line {exc.lineno} of the block)."
                ),
                line_number=line_no,
            ))

    return warnings


def _extract_defined_symbols_from_code_blocks(text: str) -> set[str]:
    """Parse python code blocks to extract functions, classes, and variables defined in them."""
    defined = set()
    blocks = re.findall(r"```python\s+(.*?)\s*```", text, re.DOTALL)
    for block in blocks:
        try:
            tree = ast.parse(block)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defined.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    defined.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    defined.add(node.id)
        except Exception:
            pass
    return defined


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(text: str, result: "AnalysisResult") -> ValidationResult:
    """
    Validate generated markdown text against the analyzer's known symbols.

    Args:
        text: The generated markdown string to validate.
        result: The AnalysisResult from analyzer.analyze() for the project.

    Returns:
        A ValidationResult with the original text and any warnings found.
    """
    from pathlib import Path
    
    # 1. Base code symbols and parameter names
    known_symbols = result.all_symbol_names | result.all_parameter_names
    
    # 2. Package, directory, and module names
    for mod in result.modules:
        p = Path(mod.path)
        known_symbols.add(p.stem)
        for part in p.parts:
            known_symbols.add(Path(part).stem)
            
        # 2.5 Extract identifiers from class bases, signatures, and annotations
        for fn in mod.functions:
            for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", fn.signature):
                known_symbols.add(match.group(0))
            for arg in fn.args:
                if arg.annotation:
                    for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", arg.annotation):
                        known_symbols.add(match.group(0))
        for cls in mod.classes:
            for base in cls.bases:
                known_symbols.add(base)
                for part in base.split("."):
                    known_symbols.add(part)
            for meth in cls.methods:
                for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", meth.signature):
                    known_symbols.add(match.group(0))
                for arg in meth.args:
                    if arg.annotation:
                        for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", arg.annotation):
                            known_symbols.add(match.group(0))
                            
        # 2.6 Extract capitalized words and backticked terms from original source docstrings
        # If a developer mentioned a class like "Markup" in the docstring, it is a valid symbol.
        def _extract_from_doc(doc: str | None):
            if not doc: return
            # Extract backticked symbols from the docstring
            for name, _ in _extract_identifiers_from_text(doc):
                known_symbols.add(name)
            # Extract PascalCase/CamelCase words (likely class names)
            for match in re.finditer(r"\b[A-Z][a-zA-Z0-9_]*\b", doc):
                known_symbols.add(match.group(0))
                
        _extract_from_doc(mod.docstring)
        for fn in mod.functions:
            _extract_from_doc(fn.docstring)
        for cls in mod.classes:
            _extract_from_doc(cls.docstring)
            for meth in cls.methods:
                _extract_from_doc(meth.docstring)
            
    # 3. Symbols defined locally in markdown example code blocks
    known_symbols |= _extract_defined_symbols_from_code_blocks(text)
    
    warnings: list[ValidationWarning] = []

    warnings.extend(_check_symbols(text, known_symbols))
    warnings.extend(_check_markdown(text))
    warnings.extend(_check_code_blocks(text))

    return ValidationResult(warnings=warnings, text=text)
