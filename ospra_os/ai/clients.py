from __future__ import annotations
from typing import Optional

from ospra_os.core.settings import get_settings


def ask_ai(prompt: str, model: str = "gpt-4o-mini") -> str:
    """
    Minimal, swappable AI client. Extend as needed in Phase 4.
    """
    s = get_settings()
    if model.startswith("gpt"):
        # OpenAI
        try:
            import openai
        except Exception as exc:
            raise RuntimeError("OpenAI SDK not installed in this environment.") from exc
        openai.api_key = s.OPENAI_API_KEY
        resp = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp["choices"][0]["message"]["content"]
    elif model.startswith("claude"):
        # Anthropic Claude
        try:
            from anthropic import Anthropic
        except Exception as exc:
            raise RuntimeError("Anthropic SDK not installed in this environment.") from exc
        client = Anthropic(api_key=s.CLAUDE_API_KEY)
        msg = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )
        return msg.content[0].text
    elif model.startswith("gemini"):
        # Google Gemini
        try:
            from google import genai
        except Exception as exc:
            raise RuntimeError("Google GenAI SDK not installed in this environment.") from exc
        client = genai.Client(api_key=s.GEMINI_API_KEY)
        out = client.generate_text(model=model, prompt=prompt)
        return out.text
    else:
        raise ValueError(f"Unknown model: {model}")
