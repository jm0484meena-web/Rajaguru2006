"""Quiz: create 3 multiple-choice questions and return them as checked data."""
from .. import gemini_client
from ..utils import parse_quiz


def generate_quiz(text: str) -> list[dict]:
    prompt = (
        "Create 3 multiple-choice questions from the topic or text below.\n"
        "Each question needs exactly 4 options and one correct answer.\n"
        "Return ONLY valid JSON (no markdown) in this exact format:\n"
        '[{"question": "...", "options": ["...", "...", "...", "..."], '
        '"answer": "the correct option, copied exactly", "explanation": "one short line why"}]\n\n'
        f"Topic or text:\n{text}"
    )
    raw = gemini_client.generate(prompt, json_mode=True, temperature=0.6)
    try:
        return parse_quiz(raw)
    except Exception:
        # One automatic retry: the model sometimes returns badly formed JSON.
        raw = gemini_client.generate(prompt, json_mode=True, temperature=0.3)
        return parse_quiz(raw)
