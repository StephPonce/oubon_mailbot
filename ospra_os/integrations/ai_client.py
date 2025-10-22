from __future__ import annotations

from typing import Any

from openai import OpenAI

from ospra_os.core.settings import Settings


def ai_client() -> OpenAI:
    st = Settings()
    if not st.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=st.OPENAI_API_KEY)


def extract_message_content(response: Any) -> str:
    try:
        message = response.choices[0].message
        content = getattr(message, "content", "") or ""
        if isinstance(content, list):
            return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
        return str(content)
    except Exception:
        return ""
