"""Multi-provider AI client supporting OpenAI and Claude."""
from typing import Optional
from app.settings import Settings
from app.oubonshop_policy import get_policy_context


class AIClient:
    """
    AI client supporting multiple providers:
    - OpenAI (GPT-4o-mini, GPT-4, etc.)
    - Anthropic Claude (Claude 3.5 Sonnet, etc.)
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.system_prompt = """
You are Oubon Shop's helpful, calm, and concise support agent.
Tone: warm, professional, modern. Keep replies short unless details are needed.
If the user asks about order status, ask for order # and email; do not invent data.
Always sign emails as "Oubon Shop Support" or "Oubon Shop".
"""

    def draft_reply(self, subject: str, body: str) -> str:
        """
        Draft AI reply using available provider.

        Priority order:
        1. Claude (if API key available) - Better for nuanced customer service
        2. OpenAI (if API key available) - Fallback
        3. Template fallback (if no AI available)
        """
        # Try Claude first
        if self._has_claude():
            try:
                return self._claude_reply(subject, body)
            except Exception as e:
                print(f"Claude API error: {e}")
                # Fall through to OpenAI

        # Try OpenAI
        if self._has_openai():
            try:
                return self._openai_reply(subject, body)
            except Exception as e:
                print(f"OpenAI API error: {e}")
                # Fall through to template

        # Fallback template
        return self._template_fallback(subject)

    def _has_claude(self) -> bool:
        """Check if Claude API is configured."""
        return bool(getattr(self.settings, 'claude_api_key', None))

    def _has_openai(self) -> bool:
        """Check if OpenAI API is configured."""
        return bool(getattr(self.settings, 'openai_api_key', None))

    def _claude_reply(self, subject: str, body: str) -> str:
        """Generate reply using Claude with company policy context."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: uv pip install anthropic")

        client = Anthropic(api_key=self.settings.claude_api_key)

        # Get company policy context
        policy_context = get_policy_context()

        prompt = f"""A customer sent this email:

Subject: {subject}

Message:
{body}

Please draft a helpful, professional reply that:
1. Acknowledges their concern
2. Provides helpful next steps based on our policies below
3. Asks for any missing information (like order number)
4. Is warm and reassuring
5. Ends with "— Oubon Shop Support"

Keep it concise (2-3 short paragraphs max).

Reference our company policies as needed:
{policy_context}"""

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            temperature=0.7,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text.strip()

    def _openai_reply(self, subject: str, body: str) -> str:
        """Generate reply using OpenAI with company policy context."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: uv pip install openai")

        client = OpenAI(api_key=self.settings.openai_api_key)

        # Get company policy context
        policy_context = get_policy_context()

        prompt = f"""Subject: {subject}

Customer message:
{body}

Draft a concise, helpful reply based on our company policies below. Keep it 2-3 paragraphs. End with "— Oubon Shop Support"

Our policies:
{policy_context}"""

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        return resp.choices[0].message.content.strip()

    def _template_fallback(self, subject: str) -> str:
        """Fallback response when no AI is available."""
        return (
            "Thanks for reaching out to Oubon Shop.\n\n"
            f"We received your message about: '{subject}'.\n"
            "A support specialist will follow up shortly. "
            "If this is about an order, please include your order number and the email used at checkout.\n\n"
            "— Oubon Shop Support"
        )

    def get_provider_name(self) -> str:
        """Get the name of the active AI provider."""
        if self._has_claude():
            return "Claude 3.5 Sonnet"
        elif self._has_openai():
            return "OpenAI GPT-4o-mini"
        else:
            return "Template Fallback"
