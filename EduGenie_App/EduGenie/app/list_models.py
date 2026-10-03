"""Run:  python -m app.list_models   -> prints the models your API key can use."""
from .config import settings


def main() -> None:
    if not settings.GEMINI_API_KEY:
        print("Add GEMINI_API_KEY to your .env file first.")
        return
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    print("Models you can use (copy one into GEMINI_MODEL in .env):\n")
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        if "generateContent" in actions:
            print(" ", model.name.replace("models/", ""))


if __name__ == "__main__":
    main()
