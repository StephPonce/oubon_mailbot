"""Multi-provider AI client supporting OpenAI and Claude."""
from typing import Optional, Tuple
from ospra_os.core.settings import Settings  # Use ospra_os settings for Render compatibility
from app.oubonshop_policy import get_policy_context
from app.response_cache import get_cached_response, cache_response
import time


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

    def draft_reply(self, subject: str, body: str) -> Tuple[str, dict]:
        """
        Draft AI reply using available provider with caching and tracking.

        Returns: (response_text, metrics)

        Priority order:
        1. Cache/FAQ (instant, free)
        2. Claude (if API key available) - Better for nuanced customer service
        3. OpenAI (if API key available) - Fallback
        4. Template fallback (if no AI available)
        """
        start_time = time.time()
        metrics = {
            "tokens_used": 0,
            "estimated_cost": 0.0,
            "processing_time_ms": 0,
            "provider": "unknown",
            "cache_hit": False,
        }

        # Check cache first
        cached = get_cached_response(subject, body)
        if cached:
            metrics["provider"] = "cache"
            metrics["cache_hit"] = True
            metrics["processing_time_ms"] = (time.time() - start_time) * 1000
            return cached, metrics

        # Try Claude first
        if self._has_claude():
            try:
                response, tokens = self._claude_reply(subject, body)
                metrics["provider"] = "Claude 3.5 Sonnet"
                metrics["tokens_used"] = tokens
                metrics["estimated_cost"] = self._estimate_cost("claude", tokens)

                # Cache the response
                cache_response(subject, body, response)

                metrics["processing_time_ms"] = (time.time() - start_time) * 1000
                return response, metrics
            except Exception as e:
                print(f"Claude API error: {e}")
                # Fall through to OpenAI

        # Try OpenAI
        if self._has_openai():
            try:
                response, tokens = self._openai_reply(subject, body)
                metrics["provider"] = "OpenAI GPT-4o-mini"
                metrics["tokens_used"] = tokens
                metrics["estimated_cost"] = self._estimate_cost("openai", tokens)

                # Cache the response
                cache_response(subject, body, response)

                metrics["processing_time_ms"] = (time.time() - start_time) * 1000
                return response, metrics
            except Exception as e:
                print(f"OpenAI API error: {e}")
                # Fall through to template

        # Fallback template
        metrics["provider"] = "template"
        metrics["processing_time_ms"] = (time.time() - start_time) * 1000
        return self._template_fallback(subject), metrics

    def _estimate_cost(self, provider: str, tokens: int) -> float:
        """Estimate cost based on provider and tokens."""
        if provider == "claude":
            # Claude 3.5 Sonnet: ~$3/M input, $15/M output (approx $9/M average)
            return (tokens / 1_000_000) * 9.0
        elif provider == "openai":
            # GPT-4o-mini: ~$0.15/M input, $0.60/M output (approx $0.375/M average)
            return (tokens / 1_000_000) * 0.375
        return 0.0

    def _has_claude(self) -> bool:
        """Check if Claude API is configured."""
        return bool(getattr(self.settings, 'claude_api_key', None))

    def _has_openai(self) -> bool:
        """Check if OpenAI API is configured."""
        return bool(getattr(self.settings, 'openai_api_key', None))

    def _claude_reply(self, subject: str, body: str) -> Tuple[str, int]:
        """Generate reply using Claude with company policy context. Returns (response, tokens)."""
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: uv pip install anthropic")

        client = Anthropic(api_key=self.settings.claude_api_key)

        # Smart context - only include relevant policy sections
        policy_context = self._get_relevant_policy(subject, body)

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

        # Get token usage
        usage = message.usage
        total_tokens = usage.input_tokens + usage.output_tokens

        return message.content[0].text.strip(), total_tokens

    def _get_relevant_policy(self, subject: str, body: str) -> str:
        """Get only relevant policy sections to reduce token usage."""
        from app.oubonshop_policy import REFUND_POLICY, RETURN_POLICY, SHIPPING_POLICY, FAQ

        text = f"{subject} {body}".lower()

        # Start with basic info
        relevant_sections = []

        # Check what's relevant
        if any(word in text for word in ["refund", "money back", "return my money"]):
            relevant_sections.append(REFUND_POLICY)

        if any(word in text for word in ["return", "send back", "ship back"]):
            relevant_sections.append(RETURN_POLICY)

        if any(word in text for word in ["shipping", "delivery", "tracking", "where is", "when will arrive"]):
            relevant_sections.append(SHIPPING_POLICY)

        # If nothing specific, include FAQ highlights
        if not relevant_sections:
            relevant_sections.append("## Common Questions\n" + "\n".join(f"Q: {q}\nA: {a}\n" for q, a in list(FAQ.items())[:3]))

        return "\n\n".join(relevant_sections) if relevant_sections else get_policy_context()

    def _openai_reply(self, subject: str, body: str) -> Tuple[str, int]:
        """Generate reply using OpenAI with smart context. Returns (response, tokens)."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package not installed. Run: uv pip install openai")

        client = OpenAI(api_key=self.settings.openai_api_key)

        # Smart context - only include relevant policy sections
        policy_context = self._get_relevant_policy(subject, body)

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

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )

        # Get token usage
        usage = resp.usage
        total_tokens = usage.prompt_tokens + usage.completion_tokens

        return resp.choices[0].message.content.strip(), total_tokens

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
