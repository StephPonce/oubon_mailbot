"""
Unified AI client wrapper (OpenAI primary, optional Grok) with quota + guardrails.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List

import requests  # kept for future providers

try:
    # OpenAI >=1.0
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

try:
    import tiktoken
except Exception:
    tiktoken = None  # type: ignore

from app.database import conn
from app.settings import Settings, get_settings

SETTINGS = get_settings()


def ai_client():
    """
    Returns a provider-specific client according to AI_PROVIDER.
    Only 'openai' is enabled by default to avoid x.ai 403s.
    """
    s = get_settings()
    provider = (getattr(s, "AI_PROVIDER", "openai") or "openai").lower()

    if provider == "openai":
        if OpenAI is None:
            raise ImportError("OpenAI library missing. Run: pip install openai>=1.0.0")
        return _OpenAIWrapper(OpenAI(api_key=s.openai_api_key), s)

    # Hard-off any accidental Grok usage to prevent 403s.
    raise ValueError(f"Unsupported AI_PROVIDER '{provider}'. Set AI_PROVIDER=openai in .env")


class _OpenAICompletionsWrapper:
    def __init__(self, client_chat_completions: Any, settings: Settings):
        self._completions = client_chat_completions
        self._settings = settings

    def create(self, **payload: Any) -> Any:
        _enforce_quota(self._settings, payload.get("messages"), payload.get("model", "gpt-4o-mini"))
        return self._completions.create(**payload)


class _OpenAIChatWrapper:
    def __init__(self, client: Any, settings: Settings):
        self.completions = _OpenAICompletionsWrapper(client.chat.completions, settings)


class _OpenAIWrapper:
    def __init__(self, client: Any, settings: Settings):
        self.chat = _OpenAIChatWrapper(client, settings)


def extract_message_content(completion: Any) -> str:
    """
    Normalize completion payloads to the first message content.
    """
    if completion is None:
        return ""
    choices: Iterable[Any] | None = getattr(completion, "choices", None)
    if choices is None and isinstance(completion, dict):
        choices = completion.get("choices")
    if not choices:
        return ""
    first = next(iter(choices))
    msg: Any = getattr(first, "message", None) or (first.get("message") if isinstance(first, dict) else None)
    if not msg:
        return ""
    content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
    return content or ""


def validate_ai_response(response: str, reasonable_prices: bool = False) -> str:
    if reasonable_prices:
        prices: List[str] = re.findall(r"\$(\d+(?:\.\d{1,2})?)", response or "")
        if prices and not all(10 < float(p) < 1000 for p in prices):
            raise ValueError("AI hallucinations in prices—retry or manual")
    return response


def _estimate_prompt_tokens(messages: Any, model: str) -> int:
    if not messages:
        return 0
    parts: List[str] = []
    for m in messages:
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, list):
            c = " ".join([str(p.get("text", "")) for p in c if isinstance(p, dict)])
        if c:
            parts.append(str(c))
    text = "\n".join(parts)
    if not text:
        return 0
    if tiktoken is None:
        return len(text) // 4 + 1
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def check_quota(settings: Settings, prompt_tokens: int) -> bool:
    limit = getattr(settings, "AI_DAILY_QUOTA", 0) or 0
    if not limit:
        return True
    date_key = datetime.now().date().isoformat()
    row = conn.execute("SELECT used FROM ai_usage WHERE date = ?", (date_key,)).fetchone()
    used = row["used"] if row and hasattr(row, "__getitem__") else (row[0] if row else 0)
    if row is None:
        conn.execute("INSERT OR REPLACE INTO ai_usage (date, used) VALUES (?, 0)", (date_key,))
    if used + prompt_tokens > limit:
        return False
    conn.execute("UPDATE ai_usage SET used = ? WHERE date = ?", (used + prompt_tokens, date_key))
    conn.commit()
    return True


def _enforce_quota(settings: Settings, messages: Any, model: str) -> None:
    tokens = _estimate_prompt_tokens(messages, model)
    if tokens and not check_quota(settings, tokens):
        raise ValueError("Quota hit—preempt overspend, wait tomorrow")


__all__ = ["ai_client", "extract_message_content", "validate_ai_response", "check_quota"]
