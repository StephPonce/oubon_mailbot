from __future__ import annotations

from textwrap import dedent


def quiet_hours_ack(brand: str, signature: str) -> str:
    return dedent(
        f"""
        Hi,

        We received your message at {brand}. We’ll reply during business hours.

        {signature}
        """
    ).strip()
