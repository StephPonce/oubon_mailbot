"""
AI Provider Routes for Ospra OS
===============================

Endpoints for managing and testing AI providers.

SECURITY: All endpoints require JWT authentication.
User ID is extracted from verified JWT tokens, not query parameters.

Endpoints:
- GET /api/ai/providers - List configured AI providers
- POST /api/ai/test/{provider} - Test a specific provider

Author: OspraOS
"""

import logging
import os
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends

from ospra_os.routers import RouterRegistry
from ospra_os.auth.jwt_auth import get_current_user
from ospra_os.database import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Providers"])


# =============================================================================
# AI PROVIDER MANAGEMENT
# =============================================================================

@router.get("/providers")
async def list_ai_providers(current_user: User = Depends(get_current_user)):
    """
    List all configured AI providers and their status.

    SECURITY: Requires JWT authentication.

    Returns:
        List of providers with configuration status and capabilities
    """
    providers = []

    # Anthropic/Claude
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append({
            "id": "anthropic",
            "name": "Anthropic Claude",
            "status": "configured",
            "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            "primary": True
        })
    else:
        providers.append({
            "id": "anthropic",
            "name": "Anthropic Claude",
            "status": "not_configured",
            "env_var": "ANTHROPIC_API_KEY"
        })

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        providers.append({
            "id": "openai",
            "name": "OpenAI GPT",
            "status": "configured",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
        })
    else:
        providers.append({
            "id": "openai",
            "name": "OpenAI GPT",
            "status": "not_configured",
            "env_var": "OPENAI_API_KEY"
        })

    # Google AI
    if os.getenv("GOOGLE_AI_API_KEY"):
        providers.append({
            "id": "google",
            "name": "Google Gemini",
            "status": "configured",
            "models": ["gemini-pro", "gemini-pro-vision"]
        })
    else:
        providers.append({
            "id": "google",
            "name": "Google Gemini",
            "status": "not_configured",
            "env_var": "GOOGLE_AI_API_KEY"
        })

    # xAI
    if os.getenv("XAI_API_KEY"):
        providers.append({
            "id": "xai",
            "name": "xAI Grok",
            "status": "configured",
            "models": ["grok-1"]
        })
    else:
        providers.append({
            "id": "xai",
            "name": "xAI Grok",
            "status": "not_configured",
            "env_var": "XAI_API_KEY"
        })

    # Groq
    if os.getenv("GROQ_API_KEY"):
        providers.append({
            "id": "groq",
            "name": "Groq",
            "status": "configured",
            "models": ["llama-2-70b", "mixtral-8x7b"]
        })
    else:
        providers.append({
            "id": "groq",
            "name": "Groq",
            "status": "not_configured",
            "env_var": "GROQ_API_KEY"
        })

    configured_count = sum(1 for p in providers if p["status"] == "configured")

    return {
        "providers": providers,
        "configured_count": configured_count,
        "total_count": len(providers),
        "user_id": current_user.id
    }


@router.post("/test/{provider}")
async def test_ai_provider(
    provider: str,
    current_user: User = Depends(get_current_user)
):
    """
    Test connectivity and basic functionality of an AI provider.

    SECURITY: Requires JWT authentication.

    Args:
        provider: Provider ID (anthropic, openai, google, xai, groq)

    Returns:
        Test results including response time and sample output
    """
    import time

    provider_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_AI_API_KEY",
        "xai": "XAI_API_KEY",
        "groq": "GROQ_API_KEY"
    }

    if provider not in provider_keys:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    api_key = os.getenv(provider_keys[provider])
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider} not configured. Set {provider_keys[provider]} environment variable."
        )

    start_time = time.time()

    try:
        # Test provider with a simple prompt
        if provider == "anthropic":
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=50,
                messages=[{"role": "user", "content": "Say 'Hello from Claude' in exactly 5 words."}]
            )
            output = response.content[0].text

        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                max_tokens=50,
                messages=[{"role": "user", "content": "Say 'Hello from GPT' in exactly 5 words."}]
            )
            output = response.choices[0].message.content

        elif provider == "google":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-pro")
            response = model.generate_content("Say 'Hello from Gemini' in exactly 5 words.")
            output = response.text

        elif provider == "groq":
            from groq import Groq
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                max_tokens=50,
                messages=[{"role": "user", "content": "Say 'Hello from Groq' in exactly 5 words."}]
            )
            output = response.choices[0].message.content

        else:
            output = "Test not implemented for this provider"

        elapsed_time = time.time() - start_time

        return {
            "success": True,
            "provider": provider,
            "response_time_ms": round(elapsed_time * 1000, 2),
            "sample_output": output[:200],
            "user_id": current_user.id
        }

    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"AI provider test failed for {provider}: {e}")

        return {
            "success": False,
            "provider": provider,
            "response_time_ms": round(elapsed_time * 1000, 2),
            "error": str(e)
        }


# Register router
RouterRegistry.register(router, prefix="", tags=["AI Providers"])

logger.info("[SUCCESS] AI Providers router loaded")
