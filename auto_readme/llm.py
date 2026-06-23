"""
llm.py — Thin, provider-agnostic LLM wrapper.

Usage:
    from auto_readme.llm import generate, set_provider

    set_provider("gemini")   # or "anthropic" or "openai"
    text = generate(prompt="Write a usage section for...", system="You are...")

Provider is controlled by AUTOREADME_LLM_PROVIDER env var (default: gemini).
API key is read from GEMINI_API_KEY/GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.

Retry: one retry with 2s backoff on transient errors.
"""

from __future__ import annotations

import os
import time
from typing import Callable

# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


def _call_anthropic(prompt: str, system: str | None, model: str, max_tokens: int) -> str:
    try:
        import anthropic  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set.")

    client = anthropic.Anthropic(api_key=api_key)
    kwargs: dict = dict(
        model=model or "claude-3-5-haiku-20241022",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if system:
        kwargs["system"] = system

    message = client.messages.create(**kwargs)
    return message.content[0].text


def _call_openai(prompt: str, system: str | None, model: str, max_tokens: int) -> str:
    try:
        from openai import OpenAI  # type: ignore[import-untyped, import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "openai package not installed. Run: pip install openai"
        ) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set.")

    client = OpenAI(api_key=api_key)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model or "gpt-4o-mini",
        messages=messages,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


def _call_gemini(prompt: str, system: str | None, model: str, max_tokens: int) -> str:
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError(
            "google-generativeai package not installed. Run: pip install google-generativeai"
        ) from exc

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set.")

    genai.configure(api_key=api_key)
    model_name = model or "gemini-2.5-flash"

    client_model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system,
    )

    gen_config = None
    if max_tokens:
        gen_config = genai.types.GenerationConfig(max_output_tokens=max_tokens)

    response = client_model.generate_content(
        prompt,
        generation_config=gen_config
    )
    return response.text


# ---------------------------------------------------------------------------
# Provider registry and state
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, Callable[..., str]] = {
    "anthropic": _call_anthropic,
    "openai": _call_openai,
    "gemini": _call_gemini,
}

_current_provider: str = os.environ.get("AUTOREADME_LLM_PROVIDER", "gemini").lower()
_current_model: str = os.environ.get("AUTOREADME_LLM_MODEL", "")


def set_provider(name: str, model: str = "") -> None:
    """Switch LLM provider at runtime. name must be 'gemini', 'anthropic', or 'openai'."""
    global _current_provider, _current_model
    name = name.lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown provider {name!r}. Choose from: {list(_PROVIDERS)}")
    _current_provider = name
    if model:
        _current_model = model


def get_provider() -> str:
    return _current_provider


# ---------------------------------------------------------------------------
# Public generate function
# ---------------------------------------------------------------------------

def generate(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 1024,
    _retry: bool = True,
) -> str:
    """
    Generate text from the configured LLM provider.

    Args:
        prompt: The user-facing prompt text.
        system: Optional system prompt / instruction context.
        max_tokens: Maximum output tokens (default 1024).
        _retry: Internal flag — set False to disable retry on this call.

    Returns:
        The generated text string.

    Raises:
        RuntimeError: If the provider or API key is misconfigured.
    """
    provider_fn = _PROVIDERS[_current_provider]
    attempts = 5
    for attempt in range(attempts):
        try:
            return provider_fn(prompt, system, _current_model, max_tokens)
        except Exception as exc:
            # Don't retry configuration/packaging errors — they won't resolve
            if isinstance(exc, (RuntimeError, ImportError)):
                raise

            exc_str = str(exc)
            is_rate_limit = any(k in exc_str.lower() for k in ("429", "resourceexhausted", "quota", "rate limit", "exceeded limit"))

            if is_rate_limit and attempt < attempts - 1:
                # Free tier key has strict RPM limits. Sleep and retry.
                sleep_time = 15 + attempt * 10
                time.sleep(sleep_time)
                continue

            if _retry and attempt == 0:
                time.sleep(2)
                continue
            raise
    raise RuntimeError("Failed to generate response after all attempts")
