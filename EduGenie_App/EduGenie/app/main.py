"""EduGenie: Gemini powered learning assistant.

Run with:   uvicorn app.main:app --reload
Then open:  http://127.0.0.1:8000
"""
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from . import database
from .config import BASE_DIR, settings
from .modules.explain import explain_topic
from .modules.learning_path import LEVELS, get_learning_recommendations
from .modules.qna import answer_question
from .modules.quiz import generate_quiz
from .modules.summary import summarize_text
from .utils import AIError, UserInputError, clean_input

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="EduGenie",
    description="Gemini powered learning assistant",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
SESSION_COOKIE = "edugenie_session"

# The five tasks shown on the page. The template builds the whole UI from this list.
TASKS = [
    {
        "id": "qa", "emoji": "💬", "tab": "Ask", "title": "Ask a Question",
        "hint": "Get a short, clear answer to any study question.",
        "label": "Your question", "placeholder": "e.g. Why is the sky blue?",
        "button": "Get Answer", "endpoint": "/qa", "kind": "text", "rows": 2,
        "examples": ["Why is the sky blue?", "Which is the largest ocean?"],
    },
    {
        "id": "explain", "emoji": "🧠", "tab": "Explain", "title": "Explain a Concept",
        "hint": "Learn any topic in simple words with an everyday example.",
        "label": "Topic", "placeholder": "e.g. Photosynthesis",
        "button": "Explain", "endpoint": "/explain", "kind": "text", "rows": 2,
        "examples": ["Photosynthesis", "Binary search algorithm"],
    },
    {
        "id": "summary", "emoji": "📝", "tab": "Summarize", "title": "Summarize a Paragraph",
        "hint": "Paste a long passage and get the key points for quick revision.",
        "label": "Your text", "placeholder": "Paste the paragraph here...",
        "button": "Summarize", "endpoint": "/summarize", "kind": "text", "rows": 6,
        "examples": [],
    },
    {
        "id": "quiz", "emoji": "❓", "tab": "Quiz", "title": "Generate a Quiz",
        "hint": "Test yourself with 3 questions. Check each answer as you go.",
        "label": "Topic or text", "placeholder": "e.g. Pythagoras theorem",
        "button": "Generate Quiz", "endpoint": "/quiz", "kind": "quiz", "rows": 2,
        "examples": ["Pythagoras theorem", "Solar System"],
    },
    {
        "id": "path", "emoji": "🗺️", "tab": "Learning Path", "title": "Get a Learning Path",
        "hint": "A step-by-step plan from beginner to advanced.",
        "label": "What do you want to learn?", "placeholder": "e.g. SQL",
        "button": "Get Learning Path", "endpoint": "/learn/recommendations", "kind": "path",
        "rows": 2, "examples": ["SQL", "Python programming"], "levels": LEVELS,
    },
]


class TextIn(BaseModel):
    text: str = ""


class LearnIn(BaseModel):
    topic: str = ""
    level: str = "Beginner"


class QuizResultIn(BaseModel):
    topic: str = ""
    score: int = 0
    total: int = 3


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)


class AccountLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


def _user_for(request: Request) -> dict | None:
    return database.get_user_for_session(request.cookies.get(SESSION_COOKIE))


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.SESSION_TTL_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


# ---------- friendly error messages (shown on the page) ----------
@app.exception_handler(UserInputError)
async def user_error_handler(_request: Request, exc: UserInputError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.exception_handler(AIError)
async def ai_error_handler(_request: Request, exc: AIError):
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse({"detail": "That request was not understood. Please try again."}, status_code=422)


@app.exception_handler(database.AccountExistsError)
async def account_exists_handler(_request: Request, exc: database.AccountExistsError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(database.DatabaseError)
async def database_error_handler(_request: Request, exc: database.DatabaseError):
    return JSONResponse({"detail": str(exc)}, status_code=503)


# ---------- pages ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"tasks": TASKS, "max_chars": settings.MAX_INPUT_CHARS},
    )


@app.get("/health")
def health():
    return {"status": "ok", "api_key_set": bool(settings.GEMINI_API_KEY), "database": database.enabled()}


@app.get("/api/auth/me")
def account_status(request: Request):
    return {"user": _user_for(request)}


@app.post("/api/auth/register", status_code=201)
def register(body: AccountCreate, response: Response):
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name:
        raise UserInputError("Please enter your name.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise UserInputError("Please enter a valid email address.")
    user, token = database.register_user(name, email, body.password)
    _set_session_cookie(response, token)
    return {"user": user}


@app.post("/api/auth/login")
def login(body: AccountLogin, response: Response):
    email = body.email.strip().lower()
    credentials = database.login_user(email, body.password)
    if credentials is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user, token = credentials
    _set_session_cookie(response, token)
    return {"user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    database.revoke_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return {"logged_out": True}


@app.get("/api/dashboard")
def dashboard(request: Request):
    user = _user_for(request)
    if user is None:
        return {"authenticated": False}
    return {"authenticated": True, "user": user, **database.dashboard_data(user["id"])}


# ---------- the five features ----------
# These are normal (not async) functions on purpose: FastAPI runs them in a
# worker thread, so a slow AI call never blocks other users.
@app.post("/qa")
def qa(body: TextIn, request: Request):
    question = clean_input(body.text, settings.MAX_INPUT_CHARS, "a question")
    answer = answer_question(question)
    user = _user_for(request)
    database.save_history(user["id"] if user else None, "qa", question, answer)
    return {"answer": answer}


@app.post("/explain")
def explain(body: TextIn, request: Request):
    topic = clean_input(body.text, settings.MAX_INPUT_CHARS, "a topic")
    explanation = explain_topic(topic)
    user = _user_for(request)
    database.save_history(user["id"] if user else None, "explain", topic, explanation)
    return {"topic": topic, "explanation": explanation}


@app.post("/summarize")
def summarize(body: TextIn, request: Request):
    text = clean_input(body.text, settings.MAX_INPUT_CHARS, "some text to summarize")
    summary = summarize_text(text)
    user = _user_for(request)
    database.save_history(user["id"] if user else None, "summary", text, summary)
    return {"summary": summary}


@app.post("/quiz")
def quiz(body: TextIn, request: Request):
    text = clean_input(body.text, settings.MAX_INPUT_CHARS, "a topic or some text")
    questions = generate_quiz(text)
    user = _user_for(request)
    database.save_history(user["id"] if user else None, "quiz", text, f"{len(questions)} questions")
    return {"topic": text[:80], "questions": questions}


@app.post("/learn/recommendations")
def learn(body: LearnIn, request: Request):
    topic = clean_input(body.topic, settings.MAX_INPUT_CHARS, "a topic")
    plan = get_learning_recommendations(topic, body.level)
    user = _user_for(request)
    database.save_history(user["id"] if user else None, "path", topic, plan)
    return {"topic": topic, "level": body.level, "recommendation": plan}


# ---------- optional database features ----------
@app.post("/quiz/result")
def quiz_result(body: QuizResultIn, request: Request):
    total = max(1, min(body.total, 10))
    score = max(0, min(body.score, total))
    user = _user_for(request)
    database.save_quiz_result(user["id"] if user else None, body.topic or "Quiz", score, total)
    return {"saved": user is not None}


@app.get("/history")
def history(request: Request):
    user = _user_for(request)
    return {
        "enabled": user is not None,
        "items": database.recent_history(user["id"]) if user else [],
    }
