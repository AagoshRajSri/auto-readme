"""
test_validator.py — Tests for auto_readme.validator

Key test: a docstring that mentions a function name that doesn't exist
is caught and reported — not silently written. This is the hallucination check.

Run with: pytest tests/test_validator.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from auto_readme.analyzer import analyze
from auto_readme.validator import (
    ValidationWarning,
    validate,
    _check_code_blocks,
    _check_markdown,
    _check_symbols,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_project"


@pytest.fixture(scope="module")
def analyzed():
    return analyze(FIXTURE_DIR)


# ---------------------------------------------------------------------------
# Symbol check
# ---------------------------------------------------------------------------

class TestSymbolCheck:
    def test_real_symbol_passes(self, analyzed):
        """Text mentioning a real function name should produce no symbol errors."""
        text = "Use `greet` to produce a greeting string. Also see `DataProcessor`."
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol" and w.level == "error"]
        assert len(symbol_errors) == 0, f"Unexpected symbol errors: {symbol_errors}"

    def test_hallucinated_function_flagged(self, analyzed):
        """
        CRITICAL: A function name that does NOT exist in the codebase must be flagged.
        This is the core hallucination check.
        """
        text = "Call `definitely_not_real_function` to process your data."
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert len(symbol_errors) >= 1, (
            "Hallucinated function name was NOT caught! This is a critical failure."
        )
        assert any("definitely_not_real_function" in w.message for w in symbol_errors)

    def test_hallucinated_class_flagged(self, analyzed):
        """A made-up class name should be flagged."""
        text = "Instantiate `FakeMadeUpClass` with your config."
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert any("FakeMadeUpClass" in w.message for w in symbol_errors)

    def test_stdlib_names_not_flagged(self, analyzed):
        """Common stdlib names like None, True, str, int should not be flagged."""
        text = "Returns `None` if not found. Accepts `str` or `int` values."
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert len(symbol_errors) == 0, f"Stdlib names incorrectly flagged: {symbol_errors}"

    def test_multiple_hallucinations_all_flagged(self, analyzed):
        """Multiple fake identifiers should all be caught."""
        text = (
            "Use `ghost_function` and `PhantomClass` to process data. "
            "Then call `another_fake_method`."
        )
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        flagged = {w.message for w in symbol_errors}
        assert any("ghost_function" in m for m in flagged)
        assert any("PhantomClass" in m for m in flagged)
        assert any("another_fake_method" in m for m in flagged)

    def test_function_with_parens_detected(self, analyzed):
        """Hallucinated `fake_fn()` (with parens) should still be caught."""
        text = "Call `fake_fn()` on the result."
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert any("fake_fn" in w.message for w in symbol_errors)

    def test_mixed_real_and_fake(self, analyzed):
        """Only the fake identifier should be flagged, not the real one."""
        text = "Use `greet` for greetings, and `nonexistent_fn` for other things."
        warnings = _check_symbols(text, analyzed.all_symbol_names)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        # greet is real — should not be flagged
        assert not any("greet" in w.message for w in symbol_errors)
        # nonexistent_fn is fake — should be flagged
        assert any("nonexistent_fn" in w.message for w in symbol_errors)

    def test_parameter_name_not_flagged(self, analyzed):
        """
        Parameter names (like `name`, `greeting`) should NOT be flagged
        since they're part of the public API surface.
        """
        known = analyzed.all_symbol_names | analyzed.all_parameter_names
        text = "The `greet` function takes a `name` and optional `greeting`."
        warnings = _check_symbols(text, known)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert len(symbol_errors) == 0, f"Parameter names incorrectly flagged: {symbol_errors}"

    def test_parameter_vs_hallucination(self, analyzed):
        """
        Real parameter names should pass, but hallucinated identifiers should still fail.
        """
        known = analyzed.all_symbol_names | analyzed.all_parameter_names
        text = "Pass `name` to `nonexistent_function` to get a result."
        warnings = _check_symbols(text, known)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert any("nonexistent_function" in w.message for w in symbol_errors)

    def test_init_not_flagged(self, analyzed):
        """__init__ should not be flagged as a hallucination."""
        known = analyzed.all_symbol_names | analyzed.all_parameter_names
        text = "Call `__init__` with the correct parameters."
        warnings = _check_symbols(text, known)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert len(symbol_errors) == 0, f"__init__ incorrectly flagged: {symbol_errors}"

    def test_lowercase_hallucination_caught(self, analyzed):
        """A lowercase hallucinated function name WITHOUT underscores must be caught.

        This tests that the prose-word heuristic does NOT blind the validator
        to plausible-sounding but non-existent function names.
        """
        known = analyzed.all_symbol_names | analyzed.all_parameter_names
        text = "Call `converter` to transform the data."
        warnings = _check_symbols(text, known)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert any("converter" in w.message for w in symbol_errors), (
            "Lowercase hallucinated name 'converter' was not caught"
        )

    def test_prose_word_not_flagged(self, analyzed):
        """Common English prose words in backticks should NOT be flagged."""
        known = analyzed.all_symbol_names | analyzed.all_parameter_names
        text = "The `function` accepts a `parameter` and `returns` a result."
        warnings = _check_symbols(text, known)
        symbol_errors = [w for w in warnings if w.check == "symbol"]
        assert len(symbol_errors) == 0, f"Prose words incorrectly flagged: {symbol_errors}"


# ---------------------------------------------------------------------------
# Markdown linting check
# ---------------------------------------------------------------------------

class TestMarkdownCheck:
    def test_heading_jump_flagged(self):
        """Jumping from ## to #### without ### should be flagged."""
        text = "## Section\n\n#### Subsection\n\nSome content."
        warnings = _check_markdown(text)
        md_warnings = [w for w in warnings if w.check == "markdown"]
        assert any("jump" in w.message.lower() or "h4" in w.message for w in md_warnings), (
            f"Heading level jump not flagged. Warnings: {md_warnings}"
        )

    def test_valid_headings_no_warning(self):
        """Sequential heading levels should not produce warnings."""
        text = "## Section\n\n### Subsection\n\nContent."
        warnings = _check_markdown(text)
        md_warnings = [w for w in warnings if w.check == "markdown"]
        assert len(md_warnings) == 0

    def test_local_py_link_flagged(self):
        """A link to a local .py file should trigger a warning."""
        text = "See [utils](utils.py) for more details."
        warnings = _check_markdown(text)
        md_warnings = [w for w in warnings if w.check == "markdown"]
        assert any("utils.py" in w.message for w in md_warnings)

    def test_external_link_not_flagged(self):
        """External https:// links should not be flagged."""
        text = "See [GitHub](https://github.com/example/repo) for details."
        warnings = _check_markdown(text)
        md_warnings = [w for w in warnings if w.check == "markdown"]
        assert len(md_warnings) == 0

    def test_pyc_link_not_false_positive(self):
        """Links to .pyc files should NOT be flagged (only .py)."""
        text = "See [compiled](module.pyc) for details."
        warnings = _check_markdown(text)
        md_warnings = [w for w in warnings if w.check == "markdown" and "module.pyc" in w.message]
        assert len(md_warnings) == 0, f".pyc produced false positive: {md_warnings}"

    def test_local_rst_link_flagged(self):
        """A link to a local .rst file should trigger a warning."""
        text = "See [docs](api.rst) for details."
        warnings = _check_markdown(text)
        md_warnings = [w for w in warnings if w.check == "markdown"]
        assert any("api.rst" in w.message for w in md_warnings)


# ---------------------------------------------------------------------------
# Code block syntax check
# ---------------------------------------------------------------------------

class TestCodeBlockCheck:
    def test_valid_python_block_passes(self):
        text = "```python\nresult = greet('World')\nprint(result)\n```"
        warnings = _check_code_blocks(text)
        assert len(warnings) == 0

    def test_invalid_python_block_flagged(self):
        """A Python code block with a syntax error should be flagged."""
        text = "```python\ndef broken(\n    pass\n```"
        warnings = _check_code_blocks(text)
        syntax_errors = [w for w in warnings if w.check == "syntax"]
        assert len(syntax_errors) >= 1, "Syntax error in code block was not caught"

    def test_non_python_block_not_checked(self):
        """A bash/shell code block should not be syntax-checked."""
        text = "```bash\npip install auto-readme\n```"
        warnings = _check_code_blocks(text)
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Full validate() integration
# ---------------------------------------------------------------------------

class TestValidateIntegration:
    def test_clean_text_returns_ok(self, analyzed):
        text = "Use `greet` and `DataProcessor` for processing."
        vr = validate(text, analyzed)
        assert vr.ok
        assert vr.text == text

    def test_hallucinated_text_has_errors(self, analyzed):
        text = "Call `totally_made_up_function` to do things."
        vr = validate(text, analyzed)
        assert vr.has_errors is True
        assert not vr.ok
        assert len(vr.warnings) >= 1

    def test_validation_result_preserves_text(self, analyzed):
        """The original text must be unchanged in the result."""
        text = "## Usage\n\nCall `greet` to greet someone."
        vr = validate(text, analyzed)
        assert vr.text == text

    def test_warning_str_format(self, analyzed):
        """ValidationWarning.__str__ should include level, check, and message."""
        w = ValidationWarning(level="error", check="symbol", message="fake", line_number=5)
        s = str(w)
        assert "ERROR" in s
        assert "symbol" in s
        assert "line 5" in s
