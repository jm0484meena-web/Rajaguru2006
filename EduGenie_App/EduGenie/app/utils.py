"""Small helpers: input checks and cleaning/validating the AI's JSON."""
import json
import re

LETTERS = ["A", "B", "C", "D"]


class UserInputError(ValueError):
    """The user sent something we cannot use (shown to them as a friendly message)."""


class AIError(RuntimeError):
    """The AI service failed. The message is safe to show to the user."""


def clean_input(text: str | None, max_chars: int, what: str = "some text") -> str:
    """Trim the text and make sure it is not empty or too long."""
    text = (text or "").strip()
    if not text:
        raise UserInputError(f"Please type {what} first.")
    if len(text) > max_chars:
        raise UserInputError(
            f"That is a bit long ({len(text)} characters). Please keep it under {max_chars}."
        )
    return text


def clean_json_block(text: str) -> str:
    """Remove ```json ... ``` fences that models sometimes add around JSON."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_quiz(raw: str) -> list[dict]:
    """Turn the AI's reply into a checked list of quiz questions.

    Every question is returned as:
      {"question": str, "options": [4 strings], "answer": one of the options, "explanation": str}
    Raises AIError if the reply is not usable, so the app can show a retry message.
    """
    try:
        data = json.loads(clean_json_block(raw))
    except (json.JSONDecodeError, TypeError):
        raise AIError("The quiz came back in a strange format. Please try again.")

    if isinstance(data, dict):  # sometimes wrapped as {"questions": [...]}
        data = data.get("questions", [])
    if not isinstance(data, list) or not data:
        raise AIError("The quiz came back empty. Please try again.")

    questions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = [str(o).strip() for o in item.get("options", []) if str(o).strip()]
        answer = str(item.get("answer", "")).strip()
        if not question or len(options) != 4:
            continue

        # The model may answer with a letter ("B") instead of the option text.
        if answer.upper() in LETTERS:
            answer = options[LETTERS.index(answer.upper())]
        if answer not in options:
            continue

        questions.append(
            {
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": str(item.get("explanation", "")).strip(),
            }
        )

    if not questions:
        raise AIError("The quiz could not be understood. Please try again.")
    return questions[:3]
