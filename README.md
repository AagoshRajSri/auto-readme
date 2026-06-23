# auto-readme

A CLI tool that generates and maintains specific sections of a `README.md` by statically analyzing a Python codebase and using an LLM (such as Google Gemini, Anthropic Claude, or OpenAI GPT) to write the prose. It performs a validation pass that catches hallucinated references before anything is written to disk.

This README is self-maintained (dogfooded) by running `auto-readme` on itself!

<!-- AUTO-README:INSTALLATION:START -->
### Installation

Install `auto-readme` directly from the source repository in editable mode:

```bash
git clone https://github.com/yourusername/auto-readme.git
cd auto-readme
pip install -e .
```

To include developer dependencies (for running tests and coverage):
```bash
pip install -e .[dev]
```

To enable OpenAI or Anthropic provider support:
```bash
pip install -e .[openai]
# or
pip install -e .[dev,openai]
```
<!-- AUTO-README:INSTALLATION:END -->

<!-- AUTO-README:USAGE:START -->
### Usage

To generate or update documentation for your project, use the `generate` command:

```bash
# Generate all sections (Installation, Usage, API Reference) using Gemini (default)
auto-readme generate --path /path/to/your/project

# Generate specific sections using OpenAI
auto-readme generate --path /path/to/your/project --section installation,usage --provider openai

# Run a dry-run to preview changes in stdout without writing to README.md
auto-readme generate --path /path/to/your/project --dry-run
```

#### CLI Options
* `--path`: Path to the Python project (required).
* `--section`: Comma-separated list of sections to build (`installation`, `usage`, `api`). Defaults to all.
* `--provider`: LLM provider (`gemini`, `anthropic`, `openai`). Defaults to `gemini`.
* `--model`: Specific model name override (e.g. `gemini-2.5-flash`, `gpt-4o-mini`).
* `--force`: Override validation check warnings/errors and write the changes anyway.
* `--dry-run`: Print the final merged README to stdout without modifying `README.md`.
<!-- AUTO-README:USAGE:END -->

<!-- AUTO-README:API:START -->
### API Reference

#### Module: `auto_readme.analyzer`
Statically parses a Python codebase using the `ast` module to extract classes, methods, functions, their signatures, and docstrings.

* **`analyze(project_root: str | Path) -> AnalysisResult`**: Analyzes all Python files under `project_root`, skipping test files and excluded directories like `venv`.
* **`AnalysisResult`**: Data class containing lists of discovered modules and identified entry points.
  * `all_symbol_names`: Set of all public function, class, and method names.
  * `all_parameter_names`: Set of all argument names for public functions and methods.

#### Module: `auto_readme.validator`
Performs verification checks on the generated documentation to prevent LLM hallucinations, syntax issues, and markdown errors.

* **`validate(text: str, result: AnalysisResult) -> ValidationResult`**: Runs symbol validation, markdown structure validation, and python code block syntax validation.
* **`ValidationResult`**: Contains the results of the validation check including a list of warnings or errors found.

#### Module: `auto_readme.merger`
Handles marker-based merging to safely insert documentation into `README.md` without affecting handwritten text.

* **`merge_sections(readme_path: Path, sections: dict[str, str]) -> str`**: Merges generated documentation strings into their corresponding marker tags in `README.md`.
<!-- AUTO-README:API:END -->

## License

MIT License. Feel free to use and distribute.
