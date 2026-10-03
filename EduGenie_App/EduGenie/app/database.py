"""SQLite persistence for accounts, sessions, learning history, and quiz scores."""
import hashlib
import hmac
import logging
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator

from .config import settings

log = logging.getLogger("edugenie.db")

PASSWORD_ITERATIONS = 310_000


class DatabaseError(RuntimeError):
    """A database operation failed and could not be completed."""


class AccountExistsError(ValueError):
    """An account already exists for the supplied email address."""


def enabled() -> bool:
    return True


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise
    except sqlite3.Error as error:
        conn.rollback()
        log.exception("SQLite operation failed")
        raise DatabaseError("The learning database is unavailable.") from error
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    path = Path(settings.DATABASE_PATH)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)

    try:
        conn = _connect()
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    task_type TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, id DESC);
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    topic TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_quiz_results_user ON quiz_results(user_id, id DESC);
                """
            )
        finally:
            conn.close()
    except sqlite3.Error as error:
        log.exception("Could not initialize SQLite database")
        raise DatabaseError("The learning database could not be initialized.") from error


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, expected = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def _create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=settings.SESSION_TTL_DAYS)).isoformat()
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at),
    )
    return token


def register_user(name: str, email: str, password: str) -> tuple[dict, str]:
    try:
        with _connection() as conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, _password_hash(password)),
            )
            row = conn.execute(
                "SELECT id, name, email FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return _public_user(row), _create_session(conn, row["id"])
    except sqlite3.IntegrityError as error:
        if "users.email" in str(error).lower() or "unique" in str(error).lower():
            raise AccountExistsError("An account with this email already exists.") from error
        raise


def login_user(email: str, password: str) -> tuple[dict, str] | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
        if row is None or not _verify_password(password, row["password_hash"] if row else ""):
            return None
        return _public_user(row), _create_session(conn, row["id"])


def get_user_for_session(token: str | None) -> dict | None:
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with _connection() as conn:
        row = conn.execute(
            """
            SELECT users.id, users.name, users.email
            FROM sessions JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash, now),
        ).fetchone()
        return _public_user(row) if row else None


def revoke_session(token: str | None) -> None:
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    with _connection() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def save_history(user_id: int | None, task: str, input_text: str, response: str) -> None:
    if user_id is None:
        return
    with _connection() as conn:
        conn.execute(
            "INSERT INTO history (user_id, task_type, input_text, response) VALUES (?, ?, ?, ?)",
            (user_id, task, input_text[:5000], response),
        )


def save_quiz_result(user_id: int | None, topic: str, score: int, total: int) -> None:
    if user_id is None:
        return
    with _connection() as conn:
        conn.execute(
            "INSERT INTO quiz_results (user_id, topic, score, total) VALUES (?, ?, ?, ?)",
            (user_id, topic[:255], score, total),
        )


def _format_date(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%d %b, %H:%M UTC")


def recent_history(user_id: int, limit: int = 8) -> list[dict]:
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT task_type, input_text, created_at FROM history
            WHERE user_id = ? ORDER BY id DESC LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [
            {
                "task": row["task_type"],
                "text": row["input_text"][:120],
                "when": _format_date(row["created_at"]),
            }
            for row in rows
        ]


def dashboard_data(user_id: int) -> dict:
    with _connection() as conn:
        totals = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM history WHERE user_id = ?) AS requests,
                (SELECT COUNT(*) FROM quiz_results WHERE user_id = ?) AS quizzes,
                (SELECT AVG(CAST(score AS REAL) * 100 / total)
                 FROM quiz_results WHERE user_id = ?) AS average_score
            """,
            (user_id, user_id, user_id),
        ).fetchone()
        history_rows = conn.execute(
            """
            SELECT task_type, input_text, created_at FROM history
            WHERE user_id = ? ORDER BY id DESC LIMIT 8
            """,
            (user_id,),
        ).fetchall()
        quiz_rows = conn.execute(
            """
            SELECT topic, score, total, created_at FROM quiz_results
            WHERE user_id = ? ORDER BY id DESC LIMIT 5
            """,
            (user_id,),
        ).fetchall()
        return {
            "requests": totals["requests"],
            "quizzes": totals["quizzes"],
            "average_score": round(totals["average_score"] or 0),
            "history": [
                {
                    "task": row["task_type"],
                    "text": row["input_text"][:120],
                    "when": _format_date(row["created_at"]),
                }
                for row in history_rows
            ],
            "quiz_results": [
                {
                    "topic": row["topic"],
                    "score": row["score"],
                    "total": row["total"],
                    "when": _format_date(row["created_at"]),
                }
                for row in quiz_rows
            ],
        }
