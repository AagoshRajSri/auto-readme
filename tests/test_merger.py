"""
test_merger.py — Tests for auto_readme.merger

Critical test: hand-written content above AND below a marker pair
is untouched after a merge.

Run with: pytest tests/test_merger.py -v
"""

from __future__ import annotations

from auto_readme.merger import merge_section, merge_sections, _wrap_section, _find_license_heading


# ---------------------------------------------------------------------------
# _wrap_section helper
# ---------------------------------------------------------------------------

class TestWrapSection:
    def test_contains_start_marker(self):
        wrapped = _wrap_section("hello", "USAGE")
        assert "<!-- AUTO-README:USAGE:START -->" in wrapped

    def test_contains_end_marker(self):
        wrapped = _wrap_section("hello", "USAGE")
        assert "<!-- AUTO-README:USAGE:END -->" in wrapped

    def test_contains_content(self):
        wrapped = _wrap_section("## Usage\nSome text.", "USAGE")
        assert "## Usage" in wrapped
        assert "Some text." in wrapped


# ---------------------------------------------------------------------------
# merge_section — replace existing markers
# ---------------------------------------------------------------------------

class TestMergeSectionReplace:
    def _make_readme(self, hand_written_above: str, hand_written_below: str, section_body: str = "OLD CONTENT") -> str:
        marker_start = "<!-- AUTO-README:USAGE:START -->"
        marker_end = "<!-- AUTO-README:USAGE:END -->"
        return (
            f"{hand_written_above}\n"
            f"{marker_start}\n"
            f"{section_body}\n"
            f"{marker_end}\n"
            f"{hand_written_below}"
        )

    def test_replaces_content_between_markers(self):
        readme = self._make_readme("# Title\n\nIntro.", "\n## License\nMIT", "OLD CONTENT")
        updated = merge_section(readme, "USAGE", "NEW CONTENT")
        assert "NEW CONTENT" in updated
        assert "OLD CONTENT" not in updated

    def test_handwritten_above_preserved(self):
        """
        CRITICAL: Content above the marker pair must be completely untouched.
        """
        above = "# My Project\n\nThis is a hand-written intro that must not change.\n"
        below = "\n## License\nMIT License"
        readme = self._make_readme(above, below)
        updated = merge_section(readme, "USAGE", "NEW CONTENT")

        # Every line of the above content must survive unchanged
        assert "# My Project" in updated
        assert "This is a hand-written intro that must not change." in updated
        assert updated.startswith("# My Project")

    def test_handwritten_below_preserved(self):
        """
        CRITICAL: Content below the marker pair must be completely untouched.
        """
        above = "# Title\n"
        below = "\n## Contributing\nPlease open a PR.\n\n## License\nMIT"
        readme = self._make_readme(above, below)
        updated = merge_section(readme, "USAGE", "NEW CONTENT")

        assert "## Contributing" in updated
        assert "Please open a PR." in updated
        assert "## License" in updated

    def test_markers_preserved_after_replace(self):
        """After replacement, markers must still be present for future runs."""
        readme = self._make_readme("# Title", "## License\nMIT")
        updated = merge_section(readme, "USAGE", "NEW CONTENT")
        assert "<!-- AUTO-README:USAGE:START -->" in updated
        assert "<!-- AUTO-README:USAGE:END -->" in updated

    def test_idempotent_on_same_content(self):
        """Running merge twice with the same content should produce stable output."""
        readme = self._make_readme("# Title\n", "\n## License\nMIT")
        run1 = merge_section(readme, "USAGE", "STABLE CONTENT")
        run2 = merge_section(run1, "USAGE", "STABLE CONTENT")
        # Content should be the same after two runs
        assert run1 == run2

    def test_multiple_sections_independent(self):
        """Merging USAGE does not affect INSTALLATION markers."""
        readme = (
            "# Title\n\n"
            "<!-- AUTO-README:INSTALLATION:START -->\npip install old\n<!-- AUTO-README:INSTALLATION:END -->\n\n"
            "<!-- AUTO-README:USAGE:START -->\nold usage\n<!-- AUTO-README:USAGE:END -->\n"
        )
        updated = merge_section(readme, "USAGE", "new usage content")
        # INSTALLATION section unchanged
        assert "pip install old" in updated
        assert "new usage content" in updated


# ---------------------------------------------------------------------------
# merge_section — insert when no markers exist
# ---------------------------------------------------------------------------

class TestMergeSectionInsert:
    def test_insert_before_license(self):
        """If no markers exist but ## License does, insert before it."""
        readme = "# Title\n\nSome content.\n\n## License\nMIT\n"
        updated = merge_section(readme, "USAGE", "## Usage\nHere is how to use it.")
        # License section still present and after the new content
        assert "## License" in updated
        assert "## Usage" in updated
        # The new content must appear before the license
        usage_pos = updated.index("## Usage")
        license_pos = updated.index("## License")
        assert usage_pos < license_pos

    def test_append_at_end_when_no_license(self):
        """If no markers and no License section, append at end."""
        readme = "# Title\n\nSome content."
        updated = merge_section(readme, "USAGE", "NEW USAGE")
        assert "NEW USAGE" in updated
        assert updated.index("NEW USAGE") > updated.index("# Title")

    def test_insert_adds_markers(self):
        """Inserting from scratch should still wrap content in markers."""
        readme = "# Title\n"
        updated = merge_section(readme, "USAGE", "content")
        assert "<!-- AUTO-README:USAGE:START -->" in updated
        assert "<!-- AUTO-README:USAGE:END -->" in updated

    def test_after_insert_replace_works(self):
        """After a fresh insert, a second merge should replace (not duplicate)."""
        readme = "# Title\n"
        after_insert = merge_section(readme, "USAGE", "first content")
        after_replace = merge_section(after_insert, "USAGE", "second content")
        assert "first content" not in after_replace
        assert "second content" in after_replace
        # Should only have ONE set of markers
        assert after_replace.count("<!-- AUTO-README:USAGE:START -->") == 1


# ---------------------------------------------------------------------------
# merge_sections — multi-section dict API
# ---------------------------------------------------------------------------

class TestMergeSections:
    def test_merge_multiple_sections(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n\n## License\nMIT\n", encoding="utf-8")

        result = merge_sections(
            readme,
            {"INSTALLATION": "## Installation\npip install pkg", "USAGE": "## Usage\nRun it."},
        )
        assert "## Installation" in result
        assert "## Usage" in result
        assert "pip install pkg" in result

    def test_dry_run_does_not_write(self, tmp_path):
        readme = tmp_path / "README.md"
        original = "# Title\n\nOriginal content.\n"
        readme.write_text(original, encoding="utf-8")

        merge_sections(readme, {"USAGE": "NEW CONTENT"}, dry_run=True)

        # File should be unchanged
        assert readme.read_text(encoding="utf-8") == original

    def test_dry_run_returns_merged_text(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Title\n", encoding="utf-8")

        result = merge_sections(readme, {"USAGE": "NEW CONTENT"}, dry_run=True)
        assert "NEW CONTENT" in result

    def test_creates_readme_if_not_exists(self, tmp_path):
        readme = tmp_path / "README.md"
        # File does not exist yet
        assert not readme.exists()

        merge_sections(readme, {"USAGE": "## Usage\nHello."})
        assert readme.exists()
        content = readme.read_text(encoding="utf-8")
        assert "## Usage" in content

    def test_license_in_code_block_not_matched(self, tmp_path):
        """A ## License heading inside a fenced code block should be ignored."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# Project\n\n```python\n## License\n# This is a comment, not the actual license.\n```\n\n## License\nMIT\n",
            encoding="utf-8",
        )
        pos = _find_license_heading(readme.read_text(encoding="utf-8"))
        assert pos is not None
        text = readme.read_text(encoding="utf-8")
        # The position should point to the REAL ## License, not the one in the code block
        after_code = text.index("## License\nMIT\n")
        assert pos == after_code, (
            "_find_license_heading pointed to code block content instead of real heading"
        )

    def test_empty_readme_no_leading_newlines(self, tmp_path):
        """An empty README should not get leading blank lines when merged."""
        readme = tmp_path / "README.md"
        readme.write_text("", encoding="utf-8")

        result = merge_sections(readme, {"USAGE": "## Usage\nHello."})
        assert not result.startswith("\n"), f"Result should not start with newlines: {result!r}"


# ---------------------------------------------------------------------------
# manifest._split_install_requires
# ---------------------------------------------------------------------------

class TestSplitInstallRequires:
    def test_split_install_requires(self):
        from auto_readme.manifest import _split_install_requires
        raw = (
            "'requests>=2.28,<3.0',"
            " 'click>=8.0',"
            "  'pydantic'"
            ",  'rich>=13.0'  "
        )
        deps = _split_install_requires(raw)
        assert deps[0] == "'requests>=2.28,<3.0'", f"Got {deps[0]}"
        assert deps[1] == "'click>=8.0'"
        assert deps[2] == "'pydantic'"
        assert deps[3] == "'rich>=13.0'"
        assert len(deps) == 4, f"Expected 4 deps, got {len(deps)}: {deps}"
