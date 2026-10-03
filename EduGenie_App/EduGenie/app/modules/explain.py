"""Explain: teach a concept in simple language."""
from .. import gemini_client


def explain_topic(topic: str) -> str:
    prompt = (
        f'Explain "{topic}" to a beginner in simple language.\n'
        "Use one everyday example. Keep it under 150 words and avoid difficult jargon."
    )
    return gemini_client.generate(prompt)
