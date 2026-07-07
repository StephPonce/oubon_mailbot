"""
LLM Analytics via OpenTelemetry + PostHog AI Observability

Sets up OpenTelemetry auto-instrumentation for Anthropic and OpenAI SDKs.
All LLM calls become $ai_generation events in PostHog AI Observability
automatically — no changes needed in individual provider files.

Design:
- Optional: silently no-ops when the OTel packages aren't installed yet
  (uv sync installs them; this keeps the app bootable in the interim).
- Distinct-ID context: the resource attribute sets a process-level fallback;
  per-request user IDs should be attached via PostHog context (new_context +
  identify_context) in the calling code.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_tracing_initialized: bool = False


def setup_llm_tracing(
    posthog_api_key: Optional[str] = None,
    posthog_host: str = "https://us.i.posthog.com",
    service_name: str = "ospra-os",
) -> bool:
    """
    Initialize OpenTelemetry tracing with PostHogSpanProcessor.

    Instruments both the Anthropic and OpenAI SDKs so every LLM call
    produces a $ai_generation event in PostHog AI Observability.

    Args:
        posthog_api_key: PostHog project token. Falls back to POSTHOG_API_KEY.
        posthog_host:    PostHog ingest host.
        service_name:    OTel service.name resource attribute.

    Returns:
        True if tracing was set up, False if packages are missing or key unset.
    """
    global _tracing_initialized

    if _tracing_initialized:
        return True

    api_key = posthog_api_key or os.getenv("POSTHOG_API_KEY")
    if not api_key:
        logger.info("[LLM-TRACING] POSTHOG_API_KEY not set — LLM tracing disabled")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider
        from posthog.ai.otel import PostHogSpanProcessor
    except ImportError:
        logger.warning(
            "[LLM-TRACING] opentelemetry-sdk or posthog[otel] not installed — "
            "run `uv sync` to enable LLM analytics"
        )
        return False

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        PostHogSpanProcessor(api_key=api_key, host=posthog_host)
    )
    trace.set_tracer_provider(provider)

    # Instrument Anthropic (claude provider)
    try:
        from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
        AnthropicInstrumentor().instrument()
        logger.info("[LLM-TRACING] Anthropic SDK instrumented")
    except ImportError:
        logger.warning(
            "[LLM-TRACING] opentelemetry-instrumentation-anthropic not installed"
        )

    # Instrument OpenAI (openai + groq + xai providers all use the OpenAI client)
    try:
        from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
        OpenAIInstrumentor().instrument()
        logger.info("[LLM-TRACING] OpenAI SDK instrumented (covers Groq + xAI too)")
    except ImportError:
        logger.warning(
            "[LLM-TRACING] opentelemetry-instrumentation-openai-v2 not installed"
        )

    _tracing_initialized = True
    logger.info(f"[LLM-TRACING] LLM observability active (host={posthog_host})")
    return True


def is_tracing_enabled() -> bool:
    """True if LLM tracing is active."""
    return _tracing_initialized


def _reset_for_tests() -> None:
    """Reset module state for test fixtures."""
    global _tracing_initialized
    _tracing_initialized = False
