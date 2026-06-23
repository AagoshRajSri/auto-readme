"""
Sample project fixture — utils.py
A handful of public and private functions, used by the test suite.
"""
from __future__ import annotations

from typing import Optional


def greet(name: str, greeting: str = "Hello") -> str:
    """
    Return a greeting string for the given name.

    Args:
        name: The person to greet.
        greeting: The greeting word to use. Defaults to 'Hello'.

    Returns:
        A formatted greeting string.
    """
    return f"{greeting}, {name}!"


def add(x: int, y: int) -> int:
    """Add two integers and return the result."""
    return x + y


def _private_helper(value: str) -> str:
    """This should NOT appear in the extracted symbols (private)."""
    return value.strip()


async def fetch_data(url: str, timeout: Optional[int] = None) -> dict:
    """
    Async function to fetch data from a URL.

    Args:
        url: The URL to fetch.
        timeout: Optional timeout in seconds.

    Returns:
        A dict with the response data.
    """
    # Placeholder — real implementation would use aiohttp
    return {"url": url, "timeout": timeout}
