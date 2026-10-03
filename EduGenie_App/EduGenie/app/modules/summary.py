"""Summary: shorten a long passage for quick revision."""
from .. import gemini_client


def summarize_text(text: str) -> str:
    prompt = (
        "Summarize the passage below in 4 to 6 short bullet points (start each with '- ') "
        "that keep the key facts. Do not add facts that are not in the passage.\n\n"
        f"Passage:\n{text}"
    )
    return gemini_client.generate(prompt)
