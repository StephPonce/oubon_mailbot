"""AI-assisted market research utilities with OpenAI or Grok backends."""
from typing import List

from app.settings import get_settings
from app.ai_client import ai_client, extract_message_content, validate_ai_response


def research_niche(prompt: str = "Suggest hot Shopify niches for 2025, focus baby/products") -> str:
    """
    Query OpenAI for niche ideas, and return the raw response text.
    """
    settings = get_settings()
    if not (settings.openai_api_key or settings.GROK_API_KEY):
        raise ValueError("Missing AI credentials in environment (OPENAI_API_KEY or GROK_API_KEY).")

    client = ai_client()
    model_name = "grok-beta" if settings.GROK_API_KEY else "gpt-4o"
    completion = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    content = extract_message_content(completion)
    content = validate_ai_response(content, reasonable_prices=False)

    if not content:
        return "No niche suggestions returned."

    lines: List[str] = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return content

    niche = lines[0]
    products_prompt = (
        f"For niche {niche}, suggest 5 products with prices and suppliers. Return concise bullet points."
    )
    completion_products = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": products_prompt}],
        temperature=0.7,
    )
    products = extract_message_content(completion_products)
    products = validate_ai_response(products, reasonable_prices=True)

    return "\n".join(lines + ["", "Product ideas:", products or "No product insights generated."])
