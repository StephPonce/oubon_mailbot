from app.settings import Settings

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

SYSTEM_PROMPT = """
You are Oubon Shop's helpful, calm, and concise support agent.
Tone: warm, professional, modern. Keep replies short unless details are needed.
If the user asks about order status, ask for order # and email; do not invent data.
Always sign emails as "Oubon Shop Support" or "Oubon Shop".
"""

def draft_reply(subject: str, body: str, settings: Settings) -> str:
    if not settings.openai_api_key or OpenAI is None:
        return (
            "Thanks for reaching out to Oubon Shop.\n\n"
            f"We received your message about: '{subject}'.\n"
            "A support specialist will follow up shortly. "
            "If this is about an order, please include your order number and the email used at checkout.\n\n"
            "— Oubon Shop Support"
        )

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"Subject: {subject}\n\nCustomer message:\n{body}\n\nDraft a concise, helpful reply."
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()
