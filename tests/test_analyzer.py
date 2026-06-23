"""
test_analyzer.py — Tests for auto_readme.analyzer

Run with: pytest tests/test_analyzer.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_readme.analyzer import analyze, AnalysisResult

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture(scope="module")
def result() -> AnalysisResult:
    """Analyze the sample_project fixture once for the whole module."""
    return analyze(FIXTURE_DIR)


# ---------------------------------------------------------------------------
# Module-level assertions
# ---------------------------------------------------------------------------

class TestModuleDiscovery:
    def test_finds_three_modules(self, result: AnalysisResult):
        """Should find utils.py, models.py, main.py (not __init__.py — no public symbols)."""
        paths = {m.path for m in result.modules}
        # All three .py files should be present
        assert any("utils" in p for p in paths), f"utils.py not found in {paths}"
        assert any("models" in p for p in paths), f"models.py not found in {paths}"
        assert any("main" in p for p in paths), f"main.py not found in {paths}"

    def test_skips_hidden_and_cache_dirs(self, result: AnalysisResult):
        """No module paths should come from __pycache__ or .git."""
        for mod in result.modules:
            assert "__pycache__" not in mod.path
            assert ".git" not in mod.path


# ---------------------------------------------------------------------------
# utils.py — functions
# ---------------------------------------------------------------------------

class TestUtilsFunctions:
    def _get_utils(self, result: AnalysisResult):
        mods = [m for m in result.modules if "utils" in m.path]
        assert mods, "utils.py module not found in result"
        return mods[0]

    def test_greet_extracted(self, result: AnalysisResult):
        mod = self._get_utils(result)
        names = [f.name for f in mod.functions]
        assert "greet" in names

    def test_add_extracted(self, result: AnalysisResult):
        mod = self._get_utils(result)
        names = [f.name for f in mod.functions]
        assert "add" in names

    def test_fetch_data_async(self, result: AnalysisResult):
        mod = self._get_utils(result)
        fns = {f.name: f for f in mod.functions}
        assert "fetch_data" in fns
        assert fns["fetch_data"].is_async is True

    def test_private_helper_excluded(self, result: AnalysisResult):
        mod = self._get_utils(result)
        names = [f.name for f in mod.functions]
        assert "_private_helper" not in names, "Private function should be excluded"

    def test_greet_signature(self, result: AnalysisResult):
        mod = self._get_utils(result)
        fns = {f.name: f for f in mod.functions}
        sig = fns["greet"].signature
        # Should contain 'name' and 'greeting' and return type 'str'
        assert "name" in sig
        assert "greeting" in sig
        assert "str" in sig

    def test_greet_docstring(self, result: AnalysisResult):
        mod = self._get_utils(result)
        fns = {f.name: f for f in mod.functions}
        doc = fns["greet"].docstring
        assert doc is not None
        assert "Return a greeting" in doc

    def test_add_signature_types(self, result: AnalysisResult):
        mod = self._get_utils(result)
        fns = {f.name: f for f in mod.functions}
        sig = fns["add"].signature
        assert "int" in sig

    def test_line_numbers_positive(self, result: AnalysisResult):
        mod = self._get_utils(result)
        for fn in mod.functions:
            assert fn.line_number > 0


# ---------------------------------------------------------------------------
# models.py — class
# ---------------------------------------------------------------------------

class TestModelsClass:
    def _get_models(self, result: AnalysisResult):
        mods = [m for m in result.modules if "models" in m.path]
        assert mods, "models.py module not found in result"
        return mods[0]

    def test_data_processor_extracted(self, result: AnalysisResult):
        mod = self._get_models(result)
        names = [c.name for c in mod.classes]
        assert "DataProcessor" in names

    def test_config_extracted(self, result: AnalysisResult):
        mod = self._get_models(result)
        names = [c.name for c in mod.classes]
        assert "Config" in names

    def test_data_processor_docstring(self, result: AnalysisResult):
        mod = self._get_models(result)
        cls_map = {c.name: c for c in mod.classes}
        doc = cls_map["DataProcessor"].docstring
        assert doc is not None
        assert "Process" in doc

    def test_data_processor_public_methods(self, result: AnalysisResult):
        mod = self._get_models(result)
        cls_map = {c.name: c for c in mod.classes}
        dp = cls_map["DataProcessor"]
        method_names = [m.name for m in dp.methods]
        # load, process, export should be present
        assert "load" in method_names
        assert "process" in method_names
        assert "export" in method_names

    def test_data_processor_private_method_excluded(self, result: AnalysisResult):
        mod = self._get_models(result)
        cls_map = {c.name: c for c in mod.classes}
        dp = cls_map["DataProcessor"]
        method_names = [m.name for m in dp.methods]
        assert "_normalize" not in method_names, "Private method should be excluded"


# ---------------------------------------------------------------------------
# main.py — entry points
# ---------------------------------------------------------------------------

class TestEntryPoints:
    def test_main_block_detected(self, result: AnalysisResult):
        """main.py has `if __name__ == '__main__':` — should be in entry_points."""
        ep_files = [ep["file"] for ep in result.entry_points]
        assert any("main" in f for f in ep_files), (
            f"No entry point detected in main.py. entry_points={result.entry_points}"
        )

    def test_entry_point_type(self, result: AnalysisResult):
        for ep in result.entry_points:
            if "main" in ep.get("file", ""):
                assert ep["type"] == "main_block"

    def test_main_function_in_main_module(self, result: AnalysisResult):
        """The main() function should be extracted from main.py."""
        mods = [m for m in result.modules if "main" in m.path]
        assert mods
        fn_names = [f.name for f in mods[0].functions]
        assert "main" in fn_names


# ---------------------------------------------------------------------------
# all_symbol_names convenience property
# ---------------------------------------------------------------------------

class TestAllSymbolNames:
    def test_all_symbols_includes_functions_and_classes(self, result: AnalysisResult):
        symbols = result.all_symbol_names
        assert "greet" in symbols
        assert "add" in symbols
        assert "DataProcessor" in symbols
        assert "Config" in symbols
        assert "main" in symbols

    def test_all_symbols_excludes_private(self, result: AnalysisResult):
        symbols = result.all_symbol_names
        assert "_private_helper" not in symbols
        assert "_normalize" not in symbols

    def test_init_included_in_methods(self, result: AnalysisResult):
        """__init__ should now be extracted as a public method."""
        mods = [m for m in result.modules if "models" in m.path]
        assert mods
        cls_map = {c.name: c for c in mods[0].classes}
        dp = cls_map["DataProcessor"]
        method_names = [m.name for m in dp.methods]
        assert "__init__" in method_names, (
            "__init__ should be included as a public constructor method"
        )

    def test_init_signature(self, result: AnalysisResult):
        """__init__ should show its parameters (minus self)."""
        mods = [m for m in result.modules if "models" in m.path]
        assert mods
        cls_map = {c.name: c for c in mods[0].classes}
        dp = cls_map["DataProcessor"]
        init_meth = next(m for m in dp.methods if m.name == "__init__")
        assert "name" in init_meth.signature
        assert "strict" in init_meth.signature
        assert "self" not in init_meth.signature

    def test_all_parameter_names(self, result: AnalysisResult):
        """Parameter names from all functions/methods should be collected."""
        params = result.all_parameter_names
        assert "name" in params        # greet() and __init__
        assert "greeting" in params    # greet()
        assert "x" in params           # add()
        assert "y" in params           # add()
        assert "url" in params         # fetch_data()
        assert "timeout" in params     # fetch_data()
        assert "records" in params     # DataProcessor.load()
        assert "strict" in params      # DataProcessor.__init__()

    def test_all_parameter_names_excludes_self(self, result: AnalysisResult):
        """self/cls should not appear in parameter names."""
        params = result.all_parameter_names
        assert "self" not in params
        assert "cls" not in params


# ---------------------------------------------------------------------------
# Signature features: * and / separators, keyword-only args
# ---------------------------------------------------------------------------

def _analyze_source(source: str) -> AnalysisResult:
    """Helper: run the analyzer on a single source string in a temp dir."""
    import tempfile
    import shutil
    tmp = Path(tempfile.mkdtemp())
    try:
        pkg = tmp / "test_pkg"
        pkg.mkdir()
        init_file = pkg / "__init__.py"
        init_file.write_text("")
        mod_file = pkg / "mod.py"
        mod_file.write_text(source)
        return analyze(pkg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestSignatureSeparators:
    def test_posonly_args_slash(self):
        source = """
def greet(name: str, /, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"
"""
        result = _analyze_source(source)
        mod = result.modules[0] if result.modules else None
        assert mod, "No module found"
        fns = {f.name: f for f in mod.functions}
        sig = fns["greet"].signature
        assert "/" in sig, f"Expected / separator in signature, got: {sig}"
        assert "name" in sig
        assert "greeting" in sig

    def test_kwonly_star(self):
        source = """
def configure(url: str, *, timeout: int = 30, retries: int = 3) -> None:
    pass
"""
        result = _analyze_source(source)
        mod = result.modules[0] if result.modules else None
        assert mod, "No module found"
        fns = {f.name: f for f in mod.functions}
        sig = fns["configure"].signature
        assert "*" in sig, f"Expected * separator in signature, got: {sig}"
        assert "timeout" in sig
        assert "retries" in sig

    def test_vararg_and_kwonly(self):
        source = """
def run(a: int, *args, verbose: bool = False) -> None:
    pass
"""
        result = _analyze_source(source)
        mod = result.modules[0] if result.modules else None
        assert mod, "No module found"
        fns = {f.name: f for f in mod.functions}
        sig = fns["run"].signature
        assert "*args" in sig, f"Expected *args in signature, got: {sig}"
        assert "verbose" in sig

    def test_kwargs(self):
        source = """
def send(url: str, **kwargs) -> dict:
    pass
"""
        result = _analyze_source(source)
        mod = result.modules[0] if result.modules else None
        assert mod, "No module found"
        fns = {f.name: f for f in mod.functions}
        sig = fns["send"].signature
        assert "**kwargs" in sig, f"Expected **kwargs in signature, got: {sig}"
