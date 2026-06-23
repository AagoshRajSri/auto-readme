"""
analyzer.py — Static analysis of a Python codebase using ast.

Extracts: top-level functions, classes, their signatures, docstrings,
file paths, line numbers, parameter names, and entry points
(if __name__ == '__main__').
Skips: private symbols (_prefix), test files, venv, __pycache__, hidden dirs.
Includes: __init__ and other well-known public dunder methods
(__new__, __call__, __enter__, __exit__, etc.).
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

SKIP_DIRS = {"venv", ".venv", "env", "__pycache__", ".git", ".tox", "build", "dist", "node_modules", ".mypy_cache", ".pytest_cache"}

# Dunder methods that are part of the public API and should NOT be treated as private
_PUBLIC_DUNDER_METHODS = {"__init__", "__new__", "__call__", "__enter__", "__exit__", "__aenter__", "__aexit__", "__str__", "__repr__", "__iter__", "__next__", "__len__", "__contains__", "__getitem__", "__setitem__", "__delitem__", "__await__"}


@dataclass
class ArgInfo:
    name: str
    annotation: str | None = None
    default: str | None = None


@dataclass
class FunctionInfo:
    name: str
    signature: str          # human-readable, e.g. "(x: int, y: str = 'hi') -> bool"
    args: list[ArgInfo] = field(default_factory=list)
    docstring: str | None = None
    file_path: str = ""
    line_number: int = 0
    is_async: bool = False


@dataclass
class ClassInfo:
    name: str
    docstring: str | None = None
    file_path: str = ""
    line_number: int = 0
    methods: list[FunctionInfo] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    path: str               # relative path from the project root
    docstring: str | None = None
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)


@dataclass
class AnalysisResult:
    entry_points: list[dict[str, Any]] = field(default_factory=list)
    modules: list[ModuleInfo] = field(default_factory=list)

    # Convenience: flat set of all known public symbol names (for validator)
    @property
    def all_symbol_names(self) -> set[str]:
        names: set[str] = set()
        for mod in self.modules:
            for fn in mod.functions:
                names.add(fn.name)
            for cls in mod.classes:
                names.add(cls.name)
                for meth in cls.methods:
                    names.add(meth.name)
        return names

    # Flat set of all parameter names across all extracted functions/methods
    @property
    def all_parameter_names(self) -> set[str]:
        params: set[str] = set()
        for mod in self.modules:
            for fn in mod.functions:
                for arg in fn.args:
                    params.add(arg.name)
            for cls in mod.classes:
                for meth in cls.methods:
                    for arg in meth.args:
                        params.add(arg.name)
        return params


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _annotation_to_str(node: ast.expr | None) -> str | None:
    """Convert an ast annotation node to a readable string."""
    if node is None:
        return None
    return ast.unparse(node)


def _default_to_str(node: ast.expr | None) -> str | None:
    """Convert an ast default value node to a readable string."""
    if node is None:
        return None
    return ast.unparse(node)


def _extract_args(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ArgInfo]:
    """Extract argument info from a function definition node."""
    args_info: list[ArgInfo] = []
    args = func_node.args

    # Build defaults list padded with None on the left
    all_args = args.posonlyargs + args.args
    n_defaults = len(args.defaults)
    padded_defaults: list[ast.expr | None] = [None] * (len(all_args) - n_defaults) + list(args.defaults)

    for arg, default in zip(all_args, padded_defaults):
        if arg.arg == "self" or arg.arg == "cls":
            continue
        args_info.append(ArgInfo(
            name=arg.arg,
            annotation=_annotation_to_str(arg.annotation),
            default=_default_to_str(default),
        ))

    # *args
    if args.vararg:
        va = args.vararg
        args_info.append(ArgInfo(
            name=f"*{va.arg}",
            annotation=_annotation_to_str(va.annotation),
        ))

    # keyword-only args with defaults
    kw_defaults: list[ast.expr | None] = list(args.kw_defaults)
    for kw_arg, kw_default in zip(args.kwonlyargs, kw_defaults):
        args_info.append(ArgInfo(
            name=kw_arg.arg,
            annotation=_annotation_to_str(kw_arg.annotation),
            default=_default_to_str(kw_default),
        ))

    # **kwargs
    if args.kwarg:
        kwa = args.kwarg
        args_info.append(ArgInfo(
            name=f"**{kwa.arg}",
            annotation=_annotation_to_str(kwa.annotation),
        ))

    return args_info


def _build_signature(func_node: ast.FunctionDef | ast.AsyncFunctionDef, args_info: list[ArgInfo]) -> str:
    """Build a human-readable signature string."""
    parts: list[str] = []

    # Positional-only args (before /)
    i = 0
    posonly_displayed = 0
    for a in func_node.args.posonlyargs:
        if a.arg in ("self", "cls"):
            continue
        info = args_info[i]
        i += 1
        token = info.name
        if info.annotation:
            token += f": {info.annotation}"
        if info.default is not None:
            token += f" = {info.default}"
        parts.append(token)
        posonly_displayed += 1

    if posonly_displayed > 0:
        parts.append("/")

    # Positional-or-keyword args
    for a in func_node.args.args:
        if a.arg in ("self", "cls"):
            continue
        info = args_info[i]
        i += 1
        token = info.name
        if info.annotation:
            token += f": {info.annotation}"
        if info.default is not None:
            token += f" = {info.default}"
        parts.append(token)

    # *vararg separator
    has_vararg = func_node.args.vararg is not None
    has_kwonly = len(func_node.args.kwonlyargs) > 0

    if has_vararg or has_kwonly:
        # Show * or *<name>
        if func_node.args.vararg:
            info = args_info[i]
            i += 1
            parts.append(info.name)
        else:
            parts.append("*")

    # Keyword-only args
    for a in func_node.args.kwonlyargs:
        info = args_info[i]
        i += 1
        token = info.name
        if info.annotation:
            token += f": {info.annotation}"
        if info.default is not None:
            token += f" = {info.default}"
        parts.append(token)

    # **kwargs
    if func_node.args.kwarg:
        info = args_info[i]
        i += 1
        parts.append(info.name)

    sig = "(" + ", ".join(parts) + ")"
    ret = _annotation_to_str(func_node.returns)
    if ret:
        sig += f" -> {ret}"
    return sig


def _is_private(name: str) -> bool:
    """Return True if name should be treated as private (excluded from docs).

    Single-underscore-prefixed names are private.
    Dunder methods (double-underscore-prefixed) are private except for
    well-known public dunders like __init__, __call__, etc.
    """
    if name.startswith("__") and name.endswith("__"):
        return name not in _PUBLIC_DUNDER_METHODS
    return name.startswith("_")


def _extract_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
) -> FunctionInfo | None:
    """Extract a FunctionInfo from a function node. Returns None for private."""
    if _is_private(node.name):
        return None
    args_info = _extract_args(node)
    sig = _build_signature(node, args_info)
    return FunctionInfo(
        name=node.name,
        signature=sig,
        args=args_info,
        docstring=ast.get_docstring(node),
        file_path=file_path,
        line_number=node.lineno,
        is_async=isinstance(node, ast.AsyncFunctionDef),
    )


def _extract_class(node: ast.ClassDef, file_path: str) -> ClassInfo | None:
    """Extract a ClassInfo from a class node. Returns None for private."""
    if _is_private(node.name):
        return None

    bases = [ast.unparse(b) for b in node.bases]
    cls_info = ClassInfo(
        name=node.name,
        docstring=ast.get_docstring(node),
        file_path=file_path,
        line_number=node.lineno,
        bases=bases,
    )

    # Collect public methods defined directly in the class body
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            meth = _extract_function(child, file_path)
            if meth is not None:
                cls_info.methods.append(meth)

    return cls_info


def _has_main_block(tree: ast.Module) -> bool:
    """Return True if the module contains `if __name__ == '__main__':` block."""
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == "__main__"
            ):
                return True
    return False


# ---------------------------------------------------------------------------
# File walker
# ---------------------------------------------------------------------------

def _is_test_file(path: Path) -> bool:
    """Return True for files that look like pytest test files."""
    name = path.stem
    return name.startswith("test_") or name.endswith("_test") or name == "conftest"


def _should_skip_dir(dir_name: str) -> bool:
    return dir_name in SKIP_DIRS or dir_name.startswith(".")


def _iter_python_files(root: Path):
    """Yield .py files under root, skipping skipped dirs and test files."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in-place so os.walk won't descend into them
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            fpath = Path(dirpath) / fname
            if _is_test_file(fpath):
                continue
            yield fpath


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze(project_root: str | Path) -> AnalysisResult:
    """
    Analyze all Python files under project_root.

    Returns an AnalysisResult containing module info and entry points.
    """
    root = Path(project_root).resolve()
    result = AnalysisResult()

    for py_file in _iter_python_files(root):
        rel_path = str(py_file.relative_to(root))
        source = py_file.read_text(encoding="utf-8", errors="replace")

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            # Skip files that can't be parsed
            continue

        mod_info = ModuleInfo(
            path=rel_path,
            docstring=ast.get_docstring(tree),
        )

        # Walk only top-level statements
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = _extract_function(node, rel_path)
                if fn is not None:
                    mod_info.functions.append(fn)
            elif isinstance(node, ast.ClassDef):
                cls = _extract_class(node, rel_path)
                if cls is not None:
                    mod_info.classes.append(cls)

        # Entry point detection: __main__ block
        if _has_main_block(tree):
            result.entry_points.append({
                "type": "main_block",
                "file": rel_path,
            })

        result.modules.append(mod_info)

    return result
