# EduGenie — your personal AI tutor

EduGenie is a full-stack learning assistant built with FastAPI, SQLite, plain
HTML/CSS/JavaScript, and Google Gemini. The main page opens directly to the
learning tools; no sign-in is needed to use them.

## Features

- Ask study questions and get clear answers with web sources.
- Explain concepts, summarize notes, generate quizzes, and create learning paths.
- Use the account and dashboard API endpoints when building an authenticated client.
- Store account passwords as salted PBKDF2 hashes and sessions in HTTP-only cookies.
- Keep account data in a local SQLite database created automatically at startup.

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder and create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install the dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and add your Gemini API key. Create a key at
   <https://aistudio.google.com>.
5. Start the app:

   ```powershell
   uvicorn app.main:app --reload
   ```

6. Open <http://127.0.0.1:8000>. API documentation is available at
   <http://127.0.0.1:8000/docs>.

The app creates `data/edugenie.sqlite3` automatically. Override the location
with `DATABASE_PATH` in `.env`. When deploying behind HTTPS, set
`SESSION_COOKIE_SECURE=true`.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key | empty |
| `GEMINI_MODEL` | Main model; check current models with `python -m app.list_models` | `gemini-3.8-flash` |
| `GEMINI_FALLBACK_MODELS` | Comma-separated fallback model names | empty |
| `MAX_INPUT_CHARS` | Maximum characters accepted per learning request | `4000` |
| `DATABASE_PATH` | SQLite file location | `data/edugenie.sqlite3` |
| `SESSION_COOKIE_SECURE` | Require HTTPS for session cookies | `false` |
| `SESSION_TTL_DAYS` | Session lifetime | `30` |

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/register` | Create an account and start a session |
| `POST` | `/api/auth/login` | Sign in |
| `POST` | `/api/auth/logout` | Sign out and revoke the session |
| `GET` | `/api/auth/me` | Get the current account |
| `GET` | `/api/dashboard` | Get the signed-in user's activity and quiz metrics |
| `POST` | `/qa` | Ask a study question |
| `POST` | `/explain` | Explain a topic |
| `POST` | `/summarize` | Summarize study text |
| `POST` | `/quiz` | Generate a multiple-choice quiz |
| `POST` | `/learn/recommendations` | Generate a learning path |
| `POST` | `/quiz/result` | Save a completed quiz score for signed-in users |
| `GET` | `/history` | Get signed-in user's recent activity |
| `GET` | `/health` | Check API and database status |

Authentication state for the account API is carried by an HTTP-only cookie.
Guest learning requests are not persisted. User activity and scores are scoped
to the authenticated account.

## Tests

Run the offline unit and API tests from this folder:

```powershell
python -m unittest discover tests -v
```

Tests use a temporary SQLite database and mocked Gemini responses; they do not
need a Gemini API key or internet access.

## Optional prompt tester

Install Gradio separately if you want to experiment with prompts:

```powershell
pip install gradio
python gradio_demo.py
```

To use the standalone dashboard, install Streamlit and run `streamlit run
dashboard.py`; sign in with the same account as the web app.

AI output can be inaccurate. Verify important information using trusted sources.
