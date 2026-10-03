"""Central settings. Values come from the .env file (see .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _database_path() -> Path:
    path = Path(os.getenv("DATABASE_PATH", "data/edugenie.sqlite3")).expanduser()
    return path if path.is_absolute() else BASE_DIR / path


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
    GEMINI_FALLBACK_MODELS: list[str] = _list(os.getenv("GEMINI_FALLBACK_MODELS", ""))
    MAX_INPUT_CHARS: int = int(os.getenv("MAX_INPUT_CHARS", "4000"))
    DATABASE_PATH: Path = _database_path()
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    SESSION_TTL_DAYS: int = int(os.getenv("SESSION_TTL_DAYS", "30"))


settings = Settings()
