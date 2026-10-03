import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import database
from app.main import app


class AccountApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_path = database.settings.DATABASE_PATH
        database.settings.DATABASE_PATH = Path(self.temp_dir.name) / "test.sqlite3"
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        database.settings.DATABASE_PATH = self.previous_path
        self.temp_dir.cleanup()

    def register(self, client, name="Student", email="student@example.com"):
        return client.post(
            "/api/auth/register",
            json={"name": name, "email": email, "password": "correct-horse-123"},
        )

    def test_register_login_and_logout(self):
        response = self.register(self.client)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["email"], "student@example.com")
        self.assertNotIn("password_hash", response.json()["user"])
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        with closing(sqlite3.connect(database.settings.DATABASE_PATH)) as conn:
            password_hash = conn.execute(
                "SELECT password_hash FROM users WHERE email = ?",
                ("student@example.com",),
            ).fetchone()[0]
        self.assertTrue(password_hash.startswith("pbkdf2_sha256$"))
        self.assertNotIn("correct-horse-123", password_hash)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["name"], "Student")

        self.assertEqual(self.client.post("/api/auth/logout").status_code, 200)
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])

        login = self.client.post(
            "/api/auth/login",
            json={"email": "STUDENT@example.com", "password": "correct-horse-123"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["user"]["id"], response.json()["user"]["id"])

    def test_rejects_duplicate_accounts_and_invalid_credentials(self):
        self.assertEqual(self.register(self.client).status_code, 201)
        duplicate = self.register(self.client, email="STUDENT@example.com")
        self.assertEqual(duplicate.status_code, 409)

        weak_password = self.client.post(
            "/api/auth/register",
            json={"name": "New", "email": "new@example.com", "password": "short"},
        )
        self.assertEqual(weak_password.status_code, 422)
        invalid_login = self.client.post(
            "/api/auth/login",
            json={"email": "student@example.com", "password": "wrong-password"},
        )
        self.assertEqual(invalid_login.status_code, 401)

    def test_dashboard_activity_and_scores_are_isolated_by_account(self):
        self.assertEqual(self.register(self.client).status_code, 201)
        self.assertTrue(
            self.client.post(
                "/quiz/result",
                json={"topic": "Algebra", "score": 2, "total": 3},
            ).json()["saved"]
        )
        database.save_history(1, "explain", "Fractions", "Parts of a whole.")

        other_client = TestClient(app)
        try:
            self.assertEqual(
                self.register(other_client, "Other student", "other@example.com").status_code,
                201,
            )
            other_dashboard = other_client.get("/api/dashboard").json()
            self.assertEqual(other_dashboard["requests"], 0)
            self.assertEqual(other_dashboard["quizzes"], 0)
            self.assertEqual(other_dashboard["history"], [])

            own_dashboard = self.client.get("/api/dashboard").json()
            self.assertEqual(own_dashboard["requests"], 1)
            self.assertEqual(own_dashboard["quizzes"], 1)
            self.assertEqual(own_dashboard["average_score"], 67)
            self.assertEqual(own_dashboard["history"][0]["text"], "Fractions")
            self.assertEqual(own_dashboard["quiz_results"][0]["topic"], "Algebra")
        finally:
            other_client.close()

    def test_guest_learning_is_available_without_saving_private_history(self):
        with mock.patch("app.main.answer_question", return_value="A clear answer."):
            response = self.client.post("/qa", json={"text": "What is gravity?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "A clear answer.")
        self.assertEqual(
            self.client.get("/api/dashboard").json(),
            {"authenticated": False},
        )
        self.assertFalse(
            self.client.post(
                "/quiz/result",
                json={"topic": "Gravity", "score": 1, "total": 1},
            ).json()["saved"]
        )

    def test_homepage_and_frontend_assets_are_served(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("Save your learning progress", page.text)
        self.assertNotIn('id="auth-form"', page.text)
        self.assertNotIn('id="dashboard-view"', page.text)
        self.assertIn("Ask a Question", page.text)
        self.assertIn("Generate a Quiz", page.text)
        self.assertEqual(self.client.get("/static/app.js").status_code, 200)
        self.assertEqual(self.client.get("/static/style.css").status_code, 200)


if __name__ == "__main__":
    unittest.main()
