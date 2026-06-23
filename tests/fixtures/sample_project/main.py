"""
Sample project fixture — main.py
Contains a __main__ block and a main() entry point.
"""
from __future__ import annotations

import sys

from .utils import greet


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for the sample project CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Exit code (0 for success).
    """
    if argv is None:
        argv = sys.argv[1:]

    name = argv[0] if argv else "World"
    print(greet(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
