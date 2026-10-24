"""Reject obvious cross-provider credential mixups before storing a secret.

A matching prefix is not proof of validity; official verification remains
the sole mechanism to mark a key as verified. Synthetic CI keys still work.
"""
import re


def key_belongs_to_other_provider(provider: str, value: str) -> bool:
    if provider == "deepseek":
        # OpenRouter API keys identify themselves with this distinct prefix.
        return value.lower().startswith("sk-or-")
    if provider == "openrouter":
        # Recognize the common 32-hex DeepSeek test/API key shape.
        return re.fullmatch(r"sk-[a-fA-F0-9]{32}", value) is not None
    return False
